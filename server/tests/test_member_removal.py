import asyncio
import pytest


@pytest.mark.parametrize('raw,expected',[
 (b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"w"}}',('u',True)),
 (b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"other"}}',('',True)),
 (b'{"type":"member:removed"}',('',True)),
 (b'{"type":"member:removed","payload":{"user_id":3}}',('',False)),
 (b'{"type":"member:removed","payload":{"user_id":"u"},"payload":{"workspace_id":"w"},"payload":null}',('u',True)),
 (b'{"type":"member:removed","payload":{"user_id":3},"payload":{"user_id":"u","workspace_id":"w"}}',('',False)),
 (b'{"TYPE":"memb\\u0065r:removed","PAYLOAD":{"USER_ID":"u","WORKSPACE_ID":"w"}}',('u',True)),
 (b'{"type":"comment:created","actor_type":"member"}',('',False)),
])
def test_removal_parser_respects_typed_merge_and_invalid_payload(raw,expected):
    from workpal_backend.realtime.member_removal import parse_removal
    assert parse_removal('w',raw)==expected


def test_snapshot_precedes_lookup_and_rejoined_targets_are_not_stopped():
    from workpal_backend.realtime.member_removal import RemovalQueue
    async def run():
        current=['old'];peers=[];stopped=[];started=asyncio.Event();release=asyncio.Event();member=[True]
        async def check(w,u):started.set();await release.wait();return member[0]
        def snapshot(w,u):return tuple(current),check
        def fanout(w,raw,event,target):peers.append((w,event,target))
        async def stop(client,notice,deadline):stopped.append((client,notice))
        queue=RemovalQueue(snapshot,fanout,stop)
        raw=b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"w"}}'
        try:
            assert queue.intercept('w',raw,'e')
            assert peers==[('w','e','u')]
            await started.wait();current.append('new');release.set();await queue.join()
            assert stopped==[]
            member[0]=False;current[:]=['old']
            queue.intercept('w',raw,'f');current.append('later');await queue.join()
            assert stopped==[('old',raw)]
        finally:await queue.close()
    asyncio.run(run())


def test_overflow_keeps_peer_order_and_lookup_error_closes_without_notice():
    from workpal_backend.realtime.member_removal import RemovalQueue
    async def run():
        started=asyncio.Queue();release=asyncio.Event();peers=[];stopped=[]
        async def check(w,u):await started.put(True);await release.wait();raise OSError('lookup unavailable')
        def snapshot(w,u):return ('c',),check
        async def stop(c,notice,deadline):stopped.append(notice)
        queue=RemovalQueue(snapshot,lambda w,r,e,u:peers.append(e),stop)
        raw=b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"w"}}'
        try:
            for i in range(2):
                queue.intercept('w',raw,str(i));await started.get()
            for i in range(2,67):queue.intercept('w',raw,str(i))
            assert queue.pending==66 and queue.dropped==1
            assert peers==[str(i) for i in range(67)]
            release.set();await queue.join()
            assert stopped==[None]*66 and queue.pending==0
        finally:release.set();await queue.close()
    asyncio.run(run())
