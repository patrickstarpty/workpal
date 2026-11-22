import asyncio
from workpal_backend.realtime.hub import Hub,Connection


class Socket:
    def __init__(self):self.frames=[];self.closes=[]
    async def send_text(self,raw):self.frames.append(raw)
    async def close(self,code):self.closes.append(code)


def attach(h,workspace,user):
    socket=Socket();c=Connection(socket,lambda:None,workspace,user);h.register(c)
    return c,socket


def test_scope_user_global_selection_exclusion_and_cross_path_dedup():
    async def run():
        h=Hub();a,sa=attach(h,'w','u');b,sb=attach(h,'x','u');c,sc=attach(h,'w','v')
        try:
            h.broadcast_to_scope('workspace','w',b'one','event')
            h.send_to_user('u',b'duplicate','', 'event')
            h.broadcast_all(b'all','w','global')
            h.unsubscribe(b,'user','u')
            h.send_to_user('u',b'only-a','x','new')
            h.broadcast_to_scope('','w',b'no','')
            await asyncio.gather(*(conn._writer.flush() for conn in [a,b,c]))
            assert sa.frames==['one','only-a']
            assert sb.frames==['duplicate','all']
            assert sc.frames==['one']
            assert h.fanout_metrics.messages_sent==5
        finally:await h.close()
    asyncio.run(run())


def test_slow_client_is_unregistered_but_queued_content_drains_before_close():
    async def run():
        h=Hub();a,sa=attach(h,'w','u');b,sb=attach(h,'x','v');callbacks=[]
        h.set_subscription_callbacks(None,lambda s,i:callbacks.append((s,i)))
        try:
            for i in range(256):assert a.try_send(str(i).encode())
            h.broadcast_all(b'overflow',event_id='e')
            assert a not in h.connections and not a.closed and b in h.connections
            assert not a.try_send(b'new')
            assert set(callbacks)=={('workspace','w'),('user','u'),('workspace_member','w:u')}
            await asyncio.gather(a._writer.flush(),b._writer.flush())
            assert sa.frames==[str(i) for i in range(256)] and sa.closes==[1005]
            assert sb.frames==['overflow'] and not sb.closes
            assert h.fanout_metrics.messages_dropped==h.fanout_metrics.slow_evictions==1
            assert not h._draining
        finally:await h.close()
    asyncio.run(run())


def test_removed_target_notice_after_confirmation_and_peers_keep_order():
    async def run():
        started=asyncio.Event();release=asyncio.Event()
        async def check(w,u):started.set();await release.wait();return False
        h=Hub(membership_check=check);target,st=attach(h,'w','u');peer,sp=attach(h,'w','v')
        raw=b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"w"}}'
        try:
            h.broadcast_to_scope('workspace','w',raw,'remove')
            await started.wait()
            late,sl=attach(h,'w','u')
            await peer._writer.flush()
            assert sp.frames==[raw.decode()] and st.frames==[]
            release.set();await h.removals.join()
            assert target.closed and st.frames==[raw.decode()]
            assert not late.closed and sl.frames==[]
        finally:release.set();await h.close()
    asyncio.run(run())


def test_rejoined_or_lookup_error_never_sends_false_removal_notice():
    async def run():
        for failure in [False,True]:
            async def check(w,u):
                if failure:raise OSError('unavailable')
                return True
            h=Hub(membership_check=check);c,s=attach(h,'w','u')
            try:
                h.broadcast_to_scope('workspace','w',b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"w"}}')
                await h.removals.join()
                assert s.frames==[] and c.closed==failure
            finally:await h.close()
    asyncio.run(run())


def test_busy_target_skips_notice_and_discards_queued_content():
    async def run():
        async def check(w,u):return False
        h=Hub(membership_check=check);c,s=attach(h,'w','u')
        await c.lock.acquire()
        try:
            c.try_send(b'must-drop')
            h.broadcast_to_scope('workspace','w',b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"w"}}')
            await h.removals.join()
            assert c.closed and s.frames==[]
        finally:c.lock.release();await h.close()
    asyncio.run(run())


def test_removal_notice_deadline_is_shared_across_all_target_sockets():
    async def run():
        async def check(w,u):return False
        h=Hub(membership_check=check);connections=[];sockets=[]
        class SlowSocket(Socket):
            async def send_text(self,raw):await asyncio.sleep(.2);self.frames.append(raw)
        for _ in range(2):
            s=SlowSocket();c=Connection(s,lambda:None,'w','u');h.register(c);connections.append(c);sockets.append(s)
        try:
            start=asyncio.get_running_loop().time()
            h.broadcast_to_scope('workspace','w',b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"w"}}')
            await h.removals.join()
            assert asyncio.get_running_loop().time()-start < .3
            assert all(c.closed for c in connections) and all(s.frames==[] for s in sockets)
        finally:await h.close()
    asyncio.run(run())


def test_hub_shutdown_during_removal_notice_still_closes_detached_transport():
    async def run():
        entered=asyncio.Event()
        class BlockedNotice(Socket):
            async def send_text(self,raw):entered.set();await asyncio.Event().wait()
        async def check(w,u):return False
        h=Hub(membership_check=check);s=BlockedNotice();c=Connection(s,lambda:None,'w','u');h.register(c)
        h.broadcast_to_scope('workspace','w',b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"w"}}')
        await entered.wait()
        assert c not in h.connections
        await h.close()
        assert s.closes==[1008]
    asyncio.run(run())


def test_hub_shutdown_joins_connection_already_closing_its_transport():
    async def run():
        entered=asyncio.Event();release=asyncio.Event();finished=[]
        class Socket:
            async def close(self,code):
                entered.set();await release.wait();finished.append(True)
        hub=Hub();connection=Connection(Socket(),lambda:None,'w','u');hub.register(connection)
        connection.finish()
        await asyncio.wait_for(entered.wait(),1)
        shutdown=asyncio.create_task(hub.close())
        await asyncio.sleep(.01)
        try:
            assert not shutdown.done(), 'Hub shutdown lost ownership of an in-progress transport close'
        finally:
            release.set()
            await asyncio.wait_for(shutdown,1)
            await connection._writer.flush()
        assert finished==[True]
        assert not hub._draining
    asyncio.run(run())
