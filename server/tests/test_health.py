from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate

def test_health(settings):
    import os
    from datetime import datetime
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        live = client.get('/health')
        assert live.status_code == 200
        assert live.json()['status'] == 'ok'
        assert live.json()['pid'] == os.getpid()
        assert datetime.fromisoformat(live.json()['started_at']).tzinfo is not None
        for route in ['/readyz','/healthz']:
            response = client.get(route)
            assert response.status_code == 200
            assert response.json()['checks'] == dict(db='ok',migrations='ok')

def test_missing_schema(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get('/readyz').status_code == 503

def test_positive_readiness_and_cleanup(settings, monkeypatch):
    from sqlalchemy import event
    from workpal_backend.infrastructure.redis import RedisResources
    async def available(self): return True
    monkeypatch.setattr(RedisResources, 'ready', available)
    migrate(settings)
    app = create_app(settings)
    closed = []
    with TestClient(app) as client:
        event.listen(app.state.database.engine, 'engine_disposed', lambda engine: closed.append(True))
        for route in ['/readyz','/healthz']:
            assert client.get(route).status_code == 200
            assert client.get(route).json()['checks'] == dict(db='ok',migrations='ok')
    assert closed == [True]
    assert app.state.redis.client.connection_pool._in_use_connections == set()


def test_live_go_wire_format(settings):
    import re
    with TestClient(create_app(settings)) as client:
        response = client.get('/health')
        assert re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', response.json()['started_at'])
        assert response.json()['commit'] == 'unknown'
        assert response.content.endswith(b'\n')
        assert int(response.headers['content-length']) == len(response.content)


def test_readiness_migration_failure_is_not_database_failure(settings, monkeypatch):
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        def broken():
            raise RuntimeError('migration query failed')
        monkeypatch.setattr(app.state.database, 'readiness', broken)
        response = client.get('/readyz')
        assert response.status_code == 503
        assert response.json() == {'status': 'not_ready', 'checks': {'db': 'ok', 'migrations': 'error'}}


def test_readiness_cache_expires_and_caches_failures(settings, monkeypatch):
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        from workpal_backend import health
        clock = [10.0]
        monkeypatch.setattr(health, 'monotonic', lambda: clock[0])
        calls = []
        def readiness():
            calls.append(True)
            return 'out_of_date' if len(calls) == 1 else 'ok'
        monkeypatch.setattr(app.state.database, 'readiness', readiness)
        assert client.get('/readyz').status_code == 503
        clock[0] = 12.999
        assert client.get('/healthz').status_code == 503
        assert len(calls) == 1
        clock[0] = 13.0
        assert client.get('/readyz').status_code == 200
        assert len(calls) == 2


def test_readiness_database_failure():
    import json
    from types import SimpleNamespace
    from workpal_backend.health import ServerHealth

    def broken():
        raise RuntimeError('database unavailable')

    health = ServerHealth()
    database = SimpleNamespace(engine=SimpleNamespace(connect=broken))
    response = health.ready(database)
    assert response.status_code == 503
    assert json.loads(response.body) == {'status': 'not_ready', 'checks': {'db': 'error', 'migrations': 'unknown'}}
    assert health.live().status_code == 200
