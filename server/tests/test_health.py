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
            assert response.status_code == 503
            assert response.json()['checks'] == dict(db='ok',migrations='ok',redis='error')

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
            assert client.get(route).json()['checks'] == dict(db='ok',migrations='ok',redis='ok')
    assert closed == [True]
    assert app.state.redis.client.connection_pool._in_use_connections == set()
