from uuid import uuid4
from fastapi.testclient import TestClient
from redis import Redis
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate
from workpal_backend.workspaces.service import create_workspace
from workpal_backend.auth.models import users
from sqlalchemy import select


def test_create_http_real_admission(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    settings.redis_url = 'redis://127.0.0.1:26379'
    settings.redis_key_prefix = 'test:mutation:' + uuid4().hex + ':'
    migrate(settings)
    redis = Redis.from_url(settings.redis_url)
    keys = []
    try:
        with TestClient(create_app(settings)) as client:
            app = client.app
            assert client.post('/api/invitations/bad/accept').status_code == 401
            login = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()
            headers = {'Authorization':'Bearer '+login['token']}
            with app.state.database.transaction() as session:
                uid = session.scalar(select(users.c.id))
                workspace = create_workspace(session, uid, 'Mutations', 'mutations')
            path = '/api/workspaces/'+workspace['id']+'/members'
            from workpal_backend.workspaces.invitation_admission import InvitationAdmission
            keys = InvitationAdmission(app.state.redis).keys(uid, workspace['id'], 'recipient@example.com')
            assert client.post(path, json={'email':'recipient@example.com'}).status_code == 403
            for value in (3, [], True):
                assert client.post(path, headers=headers, json={'email':value}).status_code == 400
            response = client.post(path, headers=headers, json={'email':' Recipient@Example.com ', 'unknown':True})
            assert response.status_code == 201, response.text
            assert response.json()['invitee_email'] == 'recipient@example.com'
            assert all(redis.zcard(key) == 1 for key in keys)
            assert client.post(path, headers=headers, json={'email':'recipient@example.com'}).status_code == 409
            assert all(redis.zcard(key) == 1 for key in keys)
            from workpal_backend.auth.tokens import issue_session
            from workpal_backend.workspaces import invitations
            from sqlalchemy import text
            recipient = str(uuid4())
            with app.state.database.transaction() as session:
                session.execute(users.insert().values(id=recipient, email='recipient@example.com', name='Recipient', created_at=invitations.stamp(), updated_at=invitations.stamp()))
            recipient_headers = {'Authorization':'Bearer '+issue_session(recipient, 'recipient@example.com', 'Recipient', settings.auth_secret, 3600)}
            accept_path = '/api/invitations/'+response.json()['id']+'/accept'
            accepted = client.post(accept_path, headers=recipient_headers, content='invalid JSON is ignored')
            assert accepted.status_code == 200, accepted.text
            assert client.post(accept_path, headers=recipient_headers).json() == accepted.json()
            with app.state.database.transaction() as session:
                assert session.scalar(select(users.c.onboarded_at).where(users.c.id == recipient))
                assert session.scalar(text("SELECT count(*) FROM outbox WHERE json_extract(envelope, '$.type') IN ('member:added','invitation:accepted')")) == 2
            assert client.post('/api/invitations/'+response.json()['id']+'/accept', headers=headers, content='invalid').status_code == 403
    finally:
        if keys:
            redis.delete(*keys)
        redis.close()
