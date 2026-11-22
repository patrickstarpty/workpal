import asyncio
import pytest


def test_disabled_cache_is_safe():
    from workpal_backend.auth.membership_cache import MembershipCache
    cache = MembershipCache()
    assert cache.get('user', 'workspace') is False
    cache.set('user', 'workspace')
    cache.invalidate('user', 'workspace')


def test_real_redis_existence_ttl_isolation_and_invalidation(isolated_relay_redis_port):
    from redis import Redis
    from workpal_backend.auth.membership_cache import MembershipCache
    client = Redis(host='127.0.0.1', port=isolated_relay_redis_port)
    try:
        cache = MembershipCache(client)
        assert cache.get('member', 'workspace') is False
        cache.set('member', 'workspace')
        key = 'mul:auth:member:member:workspace'
        assert client.get(key) == b'1'
        assert 299 <= client.ttl(key) <= 300
        assert cache.get('member', 'workspace') is True
        assert cache.get('other', 'workspace') is False
        assert cache.get('member', 'other') is False
        for value in (b'', b'0', b'arbitrary'):
            client.set(key, value)
            assert cache.get('member', 'workspace') is True
        cache.invalidate('member', 'workspace')
        assert cache.get('member', 'workspace') is False
        client.ping()  # Cache never closes a caller-owned connection.
    finally:
        client.close()


@pytest.mark.parametrize('error', [RuntimeError('redis unavailable'), asyncio.CancelledError()])
def test_redis_errors_degrade_to_database_lookup(error):
    from workpal_backend.auth.membership_cache import MembershipCache
    class Broken:
        def get(self, *args): raise error
        def set(self, *args, **kwargs): raise error
        def delete(self, *args): raise error
    cache = MembershipCache(Broken())
    assert cache.get('user', 'workspace') is False
    cache.set('user', 'workspace')
    cache.invalidate('user', 'workspace')
