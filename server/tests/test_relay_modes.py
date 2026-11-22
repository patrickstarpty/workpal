import asyncio
import json
import pytest
from workpal_backend.realtime.relay_metrics import RedisMetrics


@pytest.mark.parametrize('scope',['workspace','daemon_runtime','wecom_outbound'])
@pytest.mark.parametrize('primary_error,mirror_error',[(False,False),(True,False),(False,True),(True,True)])
def test_mirror_same_id_order_joined_errors_and_daemon_exception(scope,primary_error,mirror_error):
    from workpal_backend.realtime.relay_modes import MirroredRelay
    async def run():
        calls=[]
        class Relay:
            def __init__(self,name,fail):self.node_id=name;self.fail=fail;self.metrics=RedisMetrics()
            async def publish_with_id(self,*args):
                calls.append((self.node_id,args))
                if self.fail:raise RuntimeError(self.node_id+' failed')
        primary=Relay('primary',primary_error);mirror=Relay('mirror',mirror_error)
        relay=MirroredRelay(primary,mirror)
        error=None
        try:await relay.publish_with_id(scope,'id','exclude',b'frame','event')
        except Exception as caught:error=caught
        assert [name for name,_ in calls] == (['primary'] if scope=='daemon_runtime' else ['primary','mirror'])
        assert all(args==(scope,'id','exclude',b'frame','event') for _,args in calls)
        expected=['primary failed'] if primary_error else []
        if scope!='daemon_runtime' and mirror_error:expected.append('mirror failed')
        assert (str(error) if error else '') == '\n'.join(expected)
        expected_counts=(0,0,0) if scope=='daemon_runtime' else (int(primary_error),int(mirror_error),int(primary_error!=mirror_error))
        metrics=relay.metrics
        assert (metrics.mirror_primary_errors,metrics.mirror_secondary_errors,metrics.mirror_divergence_total)==expected_counts
    asyncio.run(run())


def test_mirror_lifecycle_orders_children_and_restores_primary_node_id():
    from workpal_backend.realtime.relay_modes import MirroredRelay
    async def run():
        calls=[];metrics=RedisMetrics()
        class Relay:
            def __init__(self,node):self.node_id=node;self.metrics=metrics
            async def start(self,parent):calls.append(('start',self.node_id));metrics.node_id=self.node_id
            def stop(self):calls.append(('stop',self.node_id))
            async def wait(self):calls.append(('wait',self.node_id))
            def set_daemon_runtime_deliverer(self,value):calls.append(('sink',self.node_id,value))
        relay=MirroredRelay(Relay('p'),Relay('m'))
        parent=asyncio.Event()
        await relay.start(parent)
        assert metrics.node_id=='p'
        relay.set_daemon_runtime_deliverer('sink')
        relay.stop();await relay.wait()
        assert calls==[('start','p'),('start','m'),('sink','p','sink'),('sink','m','sink'),('stop','p'),('stop','m'),('wait','p'),('wait','m')]
    asyncio.run(run())


def test_dual_write_local_delivery_survives_redis_failure_and_deduplicates_loopback():
    from workpal_backend.realtime.relay_modes import DualWriteBroadcaster
    from workpal_backend.realtime.hub import Hub,Connection
    from workpal_backend.realtime.relay_delivery import deliver_envelope
    from workpal_backend.realtime.relay_envelope import new_envelope
    async def run():
        frames=[];hub=Hub();writes=[]
        class Socket:
            async def send_text(self,raw):frames.append(json.loads(raw))
            async def close(self,code):pass
        connection=Connection(Socket(),lambda:None,'w','u');hub.register(connection)
        class Relay:
            async def publish_with_id(self,scope,identity,exclude,frame,event_id):
                assert hub.metrics.snapshot()['messages_sent_total']==1
                writes.append((scope,identity,exclude,frame,event_id))
                deliver_envelope(hub,new_envelope('node',scope,identity,exclude,frame,event_id))
                raise RuntimeError('lost acknowledgement')
        try:
            broadcaster=DualWriteBroadcaster(hub,Relay(),id_factory=lambda:'event')
            await broadcaster.broadcast_to_workspace('w',b'{"type":"fixture"}')
            await connection._writer.flush()
            assert frames==[{'event_id':'event','type':'fixture'}]
            assert writes==[('workspace','w','',b'{"type":"fixture"}','event')]
        finally:await hub.close()
    asyncio.run(run())


def test_dual_scope_global_is_not_the_local_global_broadcast_entrypoint():
    from workpal_backend.realtime.relay_modes import DualWriteBroadcaster
    from workpal_backend.realtime.hub import Hub,Connection
    async def run():
        frames=[];hub=Hub()
        class Socket:
            async def send_text(self,raw):frames.append(json.loads(raw))
            async def close(self,code):pass
        class Relay:
            async def publish_with_id(self,*args):raise RuntimeError('offline')
        connection=Connection(Socket(),lambda:None,'w','u');hub.register(connection)
        identities=iter(['scope-id','global-id'])
        broadcaster=DualWriteBroadcaster(hub,Relay(),id_factory=lambda:next(identities))
        try:
            await broadcaster.broadcast_to_scope('global','all',b'{"type":"scope"}')
            await connection._writer.flush()
            assert frames==[]
            await broadcaster.broadcast(b'{"type":"global"}')
            await connection._writer.flush()
            assert frames==[{'event_id':'global-id','type':'global'}]
        finally:await hub.close()
    asyncio.run(run())
