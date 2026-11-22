"""One Go-compatible per-scope Redis consumer loop.

Delivery is an async envelope callback; Hub routing and ownership of consumer
lifetimes belong to the relay. Read and write clients may use separate pools.
"""
import asyncio
from dataclasses import dataclass,replace
import logging
import time
from redis.exceptions import TimeoutError as RedisTimeoutError
from .relay_envelope import envelope_from_values,stream_key,nodes_key
from .stream_retention import RetentionConfig,TTLRefresher
from .redis_client import read_with_context

log=logging.getLogger(__name__)


class _Stopped(Exception):
    pass


async def _operation(awaitable,stop,timeout):
    task=asyncio.create_task(awaitable)
    cancelled=asyncio.create_task(stop.wait())
    try:
        done,_=await asyncio.wait((task,cancelled),timeout=max(0,timeout),return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            return task.result()
        if cancelled in done:
            raise _Stopped()
        raise TimeoutError('context deadline exceeded')
    finally:
        for pending in (task,cancelled):
            if not pending.done():pending.cancel()
        await asyncio.gather(task,cancelled,return_exceptions=True)


@dataclass
class ConsumerMetrics:
    xread_total:int=0
    xread_errors:int=0
    ack_total:int=0
    stream_missing_total:int=0
    retention_errors:int=0
    last_error:str=''


class ScopeConsumer:
    def __init__(self,write_client,read_client,node_id,scope,identity,deliver,*,
                 retention=None,ttl=None,metrics=None,clock_ns=time.time_ns):
        self.write=write_client
        self.read=read_client if read_client is not None else write_client
        self.node_id=node_id
        self.scope,self.identity=scope,identity
        self.deliver=deliver
        self.retention=(retention or RetentionConfig()).with_defaults()
        self.ttl=ttl if ttl is not None else TTLRefresher(self.retention.ttl_ns,self.retention.refresh_ns)
        self.metrics=metrics if metrics is not None else ConsumerMetrics()
        self.clock_ns=clock_ns

    def _retention_error(self,error):
        self.metrics.retention_errors+=1
        self.metrics.last_error=str(error)
        log.warning('realtime/redis: consumer retention failed: %s',error)

    async def _ensure_group(self,key,group,start):
        try:await self.write.xgroup_create(key,group,id=start,mkstream=True)
        except Exception as error:
            if 'BUSYGROUP' not in str(error):raise

    async def _setup(self,key,group,start,stop,*,recover=False):
        deadline=time.monotonic()+2
        if recover:self.ttl.forget(key)
        try:
            await _operation(self._ensure_group(key,group,start),stop,deadline-time.monotonic())
        except Exception as error:
            if recover:raise
            log.warning('realtime/redis: XGROUP CREATE failed: %s',error)
        if self.retention.enabled:
            try:await _operation(self.ttl.refresh_if_due(self.write,key),stop,deadline-time.monotonic())
            except Exception as error:
                if recover:raise
                self._retention_error(error)

    async def run(self,stop):
        key=stream_key(self.scope,self.identity)
        group='node:'+self.node_id
        cleanup=True
        try:
            await self._setup(key,group,'$',stop)
            try:
                await _operation(self.write.zadd(nodes_key(self.scope,self.identity),
                    {self.node_id:float((self.clock_ns()+90_000_000_000)//1_000_000_000)}),stop,2)
            except Exception:pass  # Go registration is best effort.
            while not stop.is_set():
                try:
                    rows=await read_with_context(self.read,'xreadgroup',stop,6,
                        group,self.node_id,{key:'>'},count=32,block=5000)
                except _Stopped:break
                except (TimeoutError,RedisTimeoutError):continue
                except Exception as error:
                    if 'NOGROUP' in str(error):
                        try:await self._setup(key,group,'0-0',stop,recover=True)
                        except Exception as repair_error:self._retention_error(repair_error)
                        else:
                            self.metrics.stream_missing_total+=1
                            continue
                    self.metrics.xread_errors+=1
                    self.metrics.last_error=str(error)
                    try:await asyncio.wait_for(stop.wait(),1)
                    except TimeoutError:continue
                    # Original Go returns directly from the backoff cancellation
                    # branch, without executing the trailing DELCONSUMER.
                    cleanup=False
                    return
                for _,messages in rows:
                    for identity,values in messages:
                        self.metrics.xread_total+=1
                        envelope,valid=envelope_from_values(values)
                        if valid:
                            await self.deliver(replace(envelope,scope=envelope.scope or self.scope,
                                                       scope_id=envelope.scope_id or self.identity))
                        try:await _operation(self.write.xack(key,group,identity),stop,1)
                        except Exception as error:log.debug('realtime/redis: XACK failed: %s',error)
                        else:self.metrics.ack_total+=1
        finally:
            if cleanup:
                try:await asyncio.wait_for(self.write.xgroup_delconsumer(key,group,self.node_id),2)
                except Exception:pass
