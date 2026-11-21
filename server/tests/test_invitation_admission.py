import asyncio
import hashlib
from types import SimpleNamespace
from uuid import uuid4

import pytest

from workpal_backend.infrastructure.redis import RedisResources
from workpal_backend.workspaces.invitation_admission import InvitationAdmission, InvitationAdmissionError, WindowLimit


def test_admission():
    async def run():
        resources = RedisResources(SimpleNamespace(redis_url='redis://localhost:26379/0', redis_key_prefix=f'test:admission:{uuid4()}:'))
        keys = set()
        def limiter(limits):
            return InvitationAdmission(resources, limits=limits)
        async def call(gate, actor='a', workspace='w', email='e@x', **kw):
            keys.update(gate.keys(actor, workspace, email))
            await gate.admit(actor, workspace, email, **kw)
        try:
            assert await resources.ready(), 'real Redis on 26379 required'
            for dimension in range(3):
                gate = limiter(tuple(WindowLimit(1 if i == dimension else 100, 10) for i in range(3)))
                a, w, e = f'a{dimension}', f'w{dimension}', f'e{dimension}@x'
                await call(gate, a, w, e, now=100)
                with pytest.raises(InvitationAdmissionError) as caught:
                    await call(gate, a, w, e, now=100.1)
                assert caught.value.status_code == 429
                assert caught.value.body['retry_after_seconds'] == 10
                await call(gate, a, w, e, now=110)
            gate = limiter((WindowLimit(2, 1),) * 3)
            assert gate.keys('n', 'n', ' E@X ')[2] == resources.key('mul:invitation:recipient:' + hashlib.sha256(b'e@x').hexdigest())
            async def attempt():
                try:
                    await call(gate, 'n', 'n', ' E@X ')
                    return True
                except InvitationAdmissionError:
                    return False
            assert sum(await asyncio.gather(*(attempt() for _ in range(30)))) == 2
            for key in gate.keys('n', 'n', 'e@x'):
                assert await resources.client.zcard(key) == 2
                assert 0 < await resources.client.pttl(key) <= 1000
            gate = limiter((WindowLimit(1, 10), WindowLimit(100, 10), WindowLimit(100, 10)))
            await call(gate, 'deny', 'first', 'first@x')
            with pytest.raises(InvitationAdmissionError):
                await call(gate, 'deny', 'untouched', 'untouched@x')
            assert not await resources.client.exists(*gate.keys('other', 'untouched', 'untouched@x')[1:])
        finally:
            if keys:
                await resources.client.delete(*keys)
            await resources.close()
    asyncio.run(run())


def test_outage():
    async def run():
        resources = RedisResources(SimpleNamespace(redis_url='redis://localhost:1/0', redis_key_prefix='test:unavailable:'))
        try:
            with pytest.raises(InvitationAdmissionError) as caught:
                await InvitationAdmission(resources).admit('a', 'w', 'e@x')
            assert caught.value.status_code == 503
            assert caught.value.headers == {'Retry-After': '5', 'Cache-Control': 'no-store'}
            assert caught.value.body == {'code': 'invitation_rate_limiter_unavailable', 'error': 'invitation service temporarily unavailable'}
        finally:
            await resources.close()
    asyncio.run(run())
