import asyncio
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session


def test_sql_pairs_do_not_cross_authorize_and_preserve_request_spelling():
    from workpal_backend.realtime.membership_queries import MembershipQueries
    w='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';v='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
    u='11111111-1111-1111-1111-111111111111';x='22222222-2222-2222-2222-222222222222'
    engine=create_engine('sqlite://')
    try:
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE members(workspace_id TEXT,user_id TEXT)'))
            conn.execute(text('INSERT INTO members VALUES (:w,:u),(:v,:x)'),dict(w=w,u=u,v=v,x=x))
        with Session(engine) as session:
            q=MembershipQueries(session)
            assert q.members([(w,x),(v,u)])=={}
            spelling=(w.upper(),u.replace('-',''))
            assert q.members([spelling,(w,u),(w,x)])=={spelling:True,(w,u):True}
            assert q.members([])=={}
            with pytest.raises(ValueError):q.members([(w,u),('invalid',u)])
            session.execute(text('DELETE FROM members WHERE user_id=:u'),dict(u=u))
            assert q.members([spelling,(w,u)])=={}
    finally:engine.dispose()


def test_cohort_deduplicates_identity_and_never_joins_inflight_lookup():
    from workpal_backend.realtime.membership_batch import MembershipBatcher
    async def run():
        entered=asyncio.Event();release=asyncio.Event();calls=[]
        async def lookup(identities):
            calls.append(identities)
            if len(calls)==1:
                entered.set();await release.wait();return {i:True for i in identities}
            return {}
        batcher=MembershipBatcher(lookup)
        try:
            first=[asyncio.create_task(batcher.authorize(('w','u'))) for _ in range(20)]
            await entered.wait()
            late=asyncio.create_task(batcher.authorize(('w','u')))
            assert await late is False
            release.set()
            assert await asyncio.gather(*first)==[True]*20
            assert calls==[[('w','u')],[('w','u')]]
        finally:await batcher.close()
    asyncio.run(run())


def test_lookup_workers_bounded_and_cancelled_requests_never_authorized():
    from workpal_backend.realtime.membership_batch import MembershipBatcher
    async def run():
        entered=asyncio.Queue();release=asyncio.Event();active=0;peak=0
        async def lookup(ids):
            nonlocal active,peak
            active+=1;peak=max(peak,active);await entered.put(ids)
            try:await release.wait();return {i:True for i in ids}
            finally:active-=1
        b=MembershipBatcher(lookup);tasks=[]
        try:
            for i in range(4):
                tasks.append(asyncio.create_task(b.authorize(('w',str(i)))))
                await asyncio.wait_for(entered.get(),1)
            fifth=asyncio.create_task(b.authorize(('w','late')));tasks.append(fifth)
            await asyncio.sleep(.02)
            assert entered.empty() and peak==4
            fifth.cancel()
            await asyncio.gather(fifth,return_exceptions=True)
            release.set()
            assert await asyncio.gather(*tasks[:4])==[True]*4
            await asyncio.sleep(.01)
            assert entered.empty()
        finally:
            release.set();await b.close()
    asyncio.run(run())


def test_lookup_errors_and_shutdown_fail_closed_without_hanging_callers():
    from workpal_backend.realtime.membership_batch import MembershipBatcher
    async def run():
        async def fail(ids):raise OSError('database unavailable')
        b=MembershipBatcher(fail)
        assert await b.authorize(('w','u')) is False
        await b.close()
        assert await b.authorize(('w','u')) is False
        entered=asyncio.Event()
        async def blocked(ids):entered.set();await asyncio.Event().wait()
        b=MembershipBatcher(blocked)
        waiting=asyncio.create_task(b.authorize(('w','u')))
        await entered.wait();await b.close()
        assert await asyncio.wait_for(waiting,.2) is False
    asyncio.run(run())


def test_hub_writers_share_fresh_cohorts_and_close_revoked_connections():
    from workpal_backend.realtime.hub import Hub,Connection
    async def run():
        calls=[];allowed=[True]
        async def lookup(ids):calls.append(ids);return {i:allowed[0] for i in ids}
        class Socket:
            def __init__(self):self.frames=[];self.closed=False
            async def send_text(self,raw):self.frames.append(raw)
            async def close(self,code):self.closed=True
        def individual():raise AssertionError('must use shared membership lookup')
        h=Hub(membership_lookup=lookup);a,b=Socket(),Socket()
        connections=[Connection(s,individual,'w','u') for s in [a,b]]
        try:
            for c in connections:h.register(c)
            await asyncio.gather(*(c.send({'type':'pong'}) for c in connections))
            assert calls==[[('w','u')]]
            assert a.frames==b.frames==['{"type":"pong"}']
            allowed[0]=False
            await asyncio.gather(*(c.send({'type':'private'}) for c in connections))
            assert calls==[[('w','u')],[('w','u')]]
            assert a.closed and b.closed and not h.connections
            assert len(a.frames)==len(b.frames)==1
        finally:await h.close()
    asyncio.run(run())
