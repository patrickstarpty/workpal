"""Actual HTTP mutation -> SQLite outbox -> Redis -> API consumer -> WebSocket."""
import json
from uuid import uuid4
import anyio
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate
from workpal_backend.infrastructure.delivery import OutboxDelivery


def test_http_mutation_reaches_websocket_and_consumer_stops(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    settings.redis_url = 'redis://127.0.0.1:26379'
    settings.redis_key_prefix = 'test:pipeline:' + uuid4().hex + ':'
    migrate(settings)
    delivery = OutboxDelivery(settings)
    app = create_app(settings)
    try:
        with TestClient(app) as client:
            login = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()
            headers = {'Authorization': 'Bearer ' + login['token']}
            workspace = client.post('/api/workspaces', headers=headers, json={'name':'Pipeline','slug':'pipeline'}).json()
            with client.websocket_connect('/ws?workspace_slug=pipeline') as ws:
                ws.send_json({'type':'ping'})
                assert ws.receive_json() == {'type':'pong'}
                updated = client.put('/api/workspaces/'+workspace['id'], headers=headers, json={'name':'Delivered'})
                assert updated.status_code == 200
                assert delivery.dispatch(app.state.database) == 1
                async def receive():
                    with anyio.fail_after(2):
                        return await ws._send_rx.receive()
                message = ws.portal.call(receive)
                assert json.loads(message['text']) == {'type':'workspace:updated', 'payload':{'workspace':updated.json()}, 'actor_id':login['user']['id'], 'actor_type':'member'}
        assert app.state.realtime_consumer_task.done()
        assert not app.state.realtime.connections
    finally:
        delivery.client.delete(delivery.channel)
        delivery.close()
