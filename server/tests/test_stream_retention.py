from workpal_backend.infrastructure.redis_cancellation import Redis
import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest


def test_defaults_keep_expiry_opt_in_and_fit_refresh_inside_ttl():
    from workpal_backend.realtime.stream_retention import RetentionConfig
    c=RetentionConfig().with_defaults()
    assert (c.max_len,c.trim_ns,c.ttl_ns,c.refresh_ns,c.maintenance_ns,c.enabled)==(2000,600_000_000_000,900_000_000_000,30_000_000_000,60_000_000_000,False)
    c=RetentionConfig(trim_ns=3,ttl_ns=3,refresh_ns=4,maintenance_ns=3,enabled=True).with_defaults()
    assert (c.ttl_ns,c.refresh_ns,c.maintenance_ns,c.enabled)==(3,1,1,True)


def test_claim_is_atomic_does_not_extend_on_duplicate_and_release_is_conditional():
    from workpal_backend.realtime.stream_retention import TTLRefresher
    r=TTLRefresher(900_000_000_000,30)
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(lambda _:r.claim('s',100),range(200)))==1
    assert not r.claim('s',129)
    assert r.claim('s',130)
    r.release('s',100)
    assert not r.claim('s',131)
    r.forget_stale(130)
    assert not r.claim('s',131)
    r.forget_stale(131)
    assert r.claim('s',131)
    r.release('s',131)
    assert r.claim('s',132)


def test_real_redis_refresh_failure_retry_repair_and_rollback(isolated_relay_redis_port):
    from workpal_backend.realtime.stream_retention import TTLRefresher
    async def run():
        client=Redis(host='127.0.0.1',port=isolated_relay_redis_port)
        key='test:retention:'+uuid4().hex
        now=[100]
        r=TTLRefresher(900_000_000_000,30,clock_ns=lambda:now[0])
        try:
            with pytest.raises(RuntimeError,match='disappeared'):
                await r.refresh_if_due(client,key)
            await client.xadd(key,{'value':'a'})
            await r.refresh_if_due(client,key)
            assert 895_000 <= await client.pttl(key) <= 900_000
            # A skipped refresh must not overwrite an independently shortened TTL.
            await client.pexpire(key,120_000)
            now[0]=129
            await r.refresh_if_due(client,key)
            assert 115_000 <= await client.pttl(key) <= 120_000
            now[0]=130
            await r.refresh_if_due(client,key)
            assert 895_000 <= await client.pttl(key) <= 900_000
            await client.pexpire(key,120_000)
            assert 115_000_000_000 <= await r.reconcile(client,key,True) <= 120_000_000_000
            assert await r.reconcile(client,key,False)==-1
            assert await client.pttl(key)==-1
            assert await r.reconcile(client,key,True)==900_000_000_000
            assert await client.xlen(key)==1
            await client.delete(key)
            assert await r.reconcile(client,key,True)==-2
            assert await r.reconcile(client,key,False)==-2
        finally:
            await client.delete(key)
            await client.aclose()
    asyncio.run(run())


def test_legacy_default_ttl_preserves_go_signed_duration_overflow():
    from workpal_backend.realtime.stream_retention import RetentionConfig
    c=RetentionConfig(trim_ns=(1<<63)-1).with_defaults()
    assert c.ttl_ns == -(1<<63)+300_000_000_000-1
    assert c.refresh_ns==c.maintenance_ns==1
