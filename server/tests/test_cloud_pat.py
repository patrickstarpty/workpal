"""Offline Fleet protocol contracts derived from Go auth/cloud_pat.go."""
import json
import pytest
import httpx
from workpal_backend.auth import cloud_pat


def verifier(body, status=200):
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(status, content=body)
    client = httpx.Client(transport=httpx.MockTransport(respond))
    return cloud_pat.CloudPATVerifier(' http://fleet.test/// ', client=client), calls


@pytest.mark.parametrize('body,kind', [
    (b'{"valid":false}', 'invalid'),
    (b'{}', 'invalid'),
    (b'null', 'invalid'),
    (b'{"valid":true}', 'unavailable'),
    (b'{"valid":"true","owner_id":"owner"}', 'unavailable'),
    (b'{"valid":true,"owner_id":7}', 'unavailable'),
    (b'{"valid":true,"owner_id":"owner"} trailing', 'unavailable'),
    (b'[]', 'unavailable'),
    (b' ' * 65537, 'unavailable'),
])
def test_fleet_response_rejections(body, kind):
    v, calls = verifier(body)
    error = cloud_pat.CloudPATInvalid if kind == 'invalid' else cloud_pat.CloudPATUnavailable
    with pytest.raises(error):
        v.verify('mcn_fixture', lambda owner: True)
    assert len(calls) == 1


@pytest.mark.parametrize('status', [201, 400, 401, 403, 404, 429, 500, 503])
def test_non_200_is_transient(status):
    v, _ = verifier(b'{"valid":false}', status)
    with pytest.raises(cloud_pat.CloudPATUnavailable):
        v.verify('mcn_fixture', lambda owner: True)


def test_wire_and_local_owner():
    v, calls = verifier(b'{"valid":true,"owner_id":"owner","instance_id":"node","instance_record_id":"record"}')
    seen = []
    identity = v.verify('mcn_fixture', lambda owner: seen.append(owner) or True)
    assert identity == {'o':'owner','i':'node','r':'record'}
    request = calls[0]
    assert request.method == 'POST'
    assert str(request.url) == 'http://fleet.test/api/v1/pat/verify'
    assert request.headers['content-type'] == request.headers['accept'] == 'application/json'
    assert request.content == b'{"token":"mcn_fixture"}'
    assert seen == ['owner']


def test_missing_owner_not_cached_and_infrastructure_is_transient():
    v, calls = verifier(b'{"valid":true,"owner_id":"owner"}')
    with pytest.raises(cloud_pat.CloudPATInvalid):
        v.verify('mcn_fixture', lambda owner: False)
    def broken(owner):
        raise OSError('offline database')
    with pytest.raises(cloud_pat.CloudPATUnavailable):
        v.verify('mcn_fixture', broken)
    assert v.verify('mcn_fixture', lambda owner: True)['o'] == 'owner'
    assert len(calls) == 3


def test_request_limit_precedes_network():
    v, calls = verifier(b'{}')
    with pytest.raises(cloud_pat.CloudPATUnavailable):
        v.verify('mcn_' + 'x' * 4096, lambda owner: True)
    assert calls == []


def test_redis_cache_positive_only(settings, isolated_relay_redis_port):
    from uuid import uuid4
    from redis import Redis
    settings.redis_url = f'redis://127.0.0.1:{isolated_relay_redis_port}'
    settings.redis_key_prefix = 'test:cloud-pat:' + uuid4().hex + ':'
    v, calls = verifier(b'{"valid":true,"owner_id":"owner"}')
    v.settings = settings
    import hashlib
    key = settings.redis_key_prefix + 'mul:auth:mcn:' + hashlib.sha256(b'mcn_fixture').hexdigest()
    with Redis.from_url(settings.redis_url) as redis:
        try:
            identity = v.verify('mcn_fixture', lambda owner: True)
            assert 0 < redis.ttl(key) <= 60
            assert v.verify('mcn_fixture', lambda owner: False) == identity
            assert len(calls) == 1
            redis.set(key, b'{"o":7}')
            assert v.verify('mcn_fixture', lambda owner: True) == identity
            assert len(calls) == 2
        finally:
            redis.delete(key)


def test_http_cloud_identity_and_human_guard(settings, monkeypatch):
    from uuid import uuid4
    from fastapi import Depends
    from fastapi.testclient import TestClient
    from workpal_backend.app import create_app
    from workpal_backend.auth.dependencies import require_principal
    from workpal_backend.auth.models import users
    from workpal_backend.infrastructure.database import migrate
    settings.cloud_url = 'http://fleet.test'
    settings.redis_url = 'redis://127.0.0.1:1'
    migrate(settings)
    app = create_app(settings)
    uid = str(uuid4())
    @app.get('/fixture/cloud')
    def identity(principal=Depends(require_principal)):
        return {'user':principal.user_id,'kind':principal.identity_kind}
    monkeypatch.setattr(cloud_pat.CloudPATVerifier, 'fetch',
                        lambda self, token: {'o':uid,'i':'node','r':'record'})
    with TestClient(app) as client:
        headers = {'Authorization':'Bearer mcn_fixture','X-Actor-Source':'human'}
        assert client.get('/fixture/cloud', headers=headers).status_code == 401
        with app.state.database.transaction() as session:
            session.execute(users.insert().values(id=uid,email='cloud@example.com',name='Cloud',
                            created_at='2026-01-01',updated_at='2026-01-01'))
        response = client.get('/fixture/cloud', headers=headers)
        assert response.status_code == 200
        assert response.json() == {'user':uid,'kind':'cloud_pat'}
        workspace = client.post('/api/workspaces', headers=headers,
                                json={'name':'Cloud owner','slug':'cloud-owner'}).json()
        assert client.get('/api/workspaces/' + workspace['id'], headers=headers).status_code == 200
        assert client.post('/api/tokens', headers=headers, json={'name':'forbidden'}).status_code == 403
        def outage(self, token):
            raise cloud_pat.CloudPATUnavailable()
        monkeypatch.setattr(cloud_pat.CloudPATVerifier, 'fetch', outage)
        response = client.get('/fixture/cloud', headers=headers)
        assert response.status_code == 503
        assert response.json() == {'error':'cloud pat verifier unavailable'}
