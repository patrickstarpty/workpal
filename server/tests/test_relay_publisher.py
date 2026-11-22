from workpal_backend.infrastructure.redis_cancellation import Redis
import asyncio
from uuid import uuid4
import pytest


def test_real_redis_publisher_preserves_envelope_and_opt_in_ttl(isolated_relay_redis_port):
    from workpal_backend.realtime.relay_publisher import RelayPublisher,PublishMetrics
    from workpal_backend.realtime.stream_retention import RetentionConfig
    from workpal_backend.realtime.relay_envelope import stream_key
    async def run():
        client=Redis(host='127.0.0.1',port=isolated_relay_redis_port)
        identity='test:'+uuid4().hex
        key=stream_key('user',identity)
        metrics=PublishMetrics()
        publisher=RelayPublisher(client,'node',metrics=metrics,clock_ns=lambda:0)
        frame=b'{ "type":"x", "actor_id":"a", "payload":9007199254740993 }'
        try:
            await publisher.publish_with_id('user',identity,'excluded',frame,'id')
            rows=await client.xrange(key)
            assert len(rows)==1
            assert rows[0][1]=={b'event_id':b'id',b'event_type':b'x',b'scope':b'user',b'scope_id':identity.encode(),b'workspace_id':b'excluded',b'actor_id':b'a',b'created_at':b'1970-01-01T00:00:00Z',b'node_id':b'node',b'payload_json':frame}
            assert await client.pttl(key)==-1
            publisher=RelayPublisher(client,'node',retention=RetentionConfig(enabled=True),metrics=metrics)
            await publisher.publish_with_id('user',identity,'',b'opaque','next')
            assert await client.xlen(key)==2
            assert 895_000 <= await client.pttl(key) <= 900_000
            assert (metrics.xadd_total,metrics.xadd_errors,metrics.retention_errors)==(2,0,0)
        finally:
            await client.delete(key)
            await client.aclose()
    asyncio.run(run())


def test_xadd_failure_propagates_but_post_write_ttl_failure_does_not():
    from workpal_backend.realtime.relay_publisher import RelayPublisher,PublishMetrics
    from workpal_backend.realtime.stream_retention import RetentionConfig
    # Fault injection at the network boundary; publisher and TTL state are real.
    class Client:
        def __init__(self):self.fail_write=True;self.expiry_calls=0;self.writes=[]
        async def xadd(self,key,values,**options):
            if self.fail_write:raise OSError('write unavailable')
            self.writes.append((key,values,options))
            return b'1-0'
        async def pexpire(self,key,ttl):
            self.expiry_calls+=1
            raise OSError('expiry unavailable')
    async def run():
        client=Client();metrics=PublishMetrics()
        publisher=RelayPublisher(client,'node',retention=RetentionConfig(max_len=7,enabled=True),metrics=metrics)
        with pytest.raises(OSError,match='write unavailable'):
            await publisher.publish_with_id('chat','c','',b'x','id')
        assert client.expiry_calls==0 and metrics.xadd_errors==1 and metrics.last_error=='write unavailable'
        client.fail_write=False
        await publisher.publish_with_id('chat','c','',b'x','id')
        await publisher.publish_with_id('chat','c','',b'x','id')
        assert len(client.writes)==2 and client.writes[0][2]=={'maxlen':7,'approximate':True}
        assert client.expiry_calls==2
        assert (metrics.xadd_total,metrics.xadd_errors,metrics.retention_errors)==(2,1,2)
        assert metrics.last_error=='expiry unavailable'
    asyncio.run(run())


def test_publish_timeout_cancels_write_and_counts_failure():
    from workpal_backend.realtime.relay_publisher import RelayPublisher,PublishMetrics
    class Client:
        def __init__(self):self.cancelled=False
        async def xadd(self,*args,**kwargs):
            try:await asyncio.Event().wait()
            finally:self.cancelled=True
    async def run():
        client=Client();metrics=PublishMetrics();publisher=RelayPublisher(client,'n',metrics=metrics)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(publisher.publish_with_id('s','i','',b'x','e'),3)
        assert client.cancelled and metrics.xadd_errors==1 and metrics.xadd_total==0
    asyncio.run(run())
