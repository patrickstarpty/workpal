import pytest
from fastapi.testclient import TestClient
from workpal_backend.app import create_app


@pytest.mark.parametrize('host,headers,status', [
    ('127.0.0.1',{},200),('::1',{},200),('::ffff:127.0.0.1',{},200),
    ('192.0.2.1',{},404),('localhost',{},404),('::1%lo0',{},404),
    ('127.0.0.1',{'x-forwarded-for':'192.0.2.1'},404),
    ('127.0.0.1',{'forwarded':'   '},200),
])
def test_loopback_metrics_access_and_snapshot(settings,host,headers,status):
    app = create_app(settings)
    with TestClient(app,client=(host,1234)) as client:
        response = client.get('/health/realtime',headers=headers)
        assert response.status_code == status
        if status == 200:
            body = response.json()
            assert body['active_connections'] == 0
            assert body['redis']['streams'] == {}
            assert body['daemonws']['wakeup_received_total'] == 0
            assert response.headers['cache-control'] == 'no-store'
            assert response.content.endswith(b'\n')
        else:
            assert response.content == b'404 page not found\n'
            assert response.headers['x-content-type-options'] == 'nosniff'


@pytest.mark.parametrize('authorization,status',[(None,401),('Bearer wrong',401),('bEaReR  fixture-token  ',200)])
def test_metrics_token_overrides_loopback_and_forwarding_policy(settings,authorization,status):
    settings.realtime_metrics_token = ' fixture-token '
    app = create_app(settings)
    with TestClient(app,client=('192.0.2.1',1234)) as client:
        headers = {'x-forwarded-for':'198.51.100.1'}
        if authorization is not None:
            headers['authorization'] = authorization
        response = client.get('/health/realtime',headers=headers)
        assert response.status_code == status
        if status == 401:
            assert response.content == b'unauthorized\n'
            assert response.headers['www-authenticate'] == 'Bearer realm="metrics"'


def test_metrics_headers_preserve_go_utf8_byte_semantics(settings):
    settings.realtime_metrics_token = 'tökén'
    app = create_app(settings)
    with TestClient(app,client=('192.0.2.1',1234)) as client:
        response = client.get('/health/realtime',headers=[(b'authorization','Bearer tökén'.encode())])
        assert response.status_code == 200
    settings.realtime_metrics_token = ''
    app = create_app(settings)
    with TestClient(app,client=('127.0.0.1',1234)) as client:
        # UTF-8 NBSP is whitespace in Go, an isolated invalid byte is not.
        assert client.get('/health/realtime',headers=[(b'forwarded',b'\xc2\xa0')]).status_code == 200
        # TestClient re-encodes invalid header bytes as UTF-8. Exercise the
        # ASGI header facade directly for the invalid-byte boundary.
        from starlette.datastructures import Headers
        from workpal_backend.realtime.health import direct_loopback
        assert not direct_loopback('127.0.0.1', Headers(raw=[(b'forwarded',b'\xa0')]))
