"""Five HTTP boundary groups against disposable SQLite and real Redis."""
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import sqlite3
import pytest
from redis import Redis
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate
from workpal_backend.auth.models import users
from workpal_backend.auth.tokens import issue_session
from workpal_backend.workspaces import invitations as svc
from workpal_backend.workspaces.models import members
from workpal_backend.workspaces.service import create_workspace
from workpal_backend.workspaces.invitation_admission import InvitationAdmission


@pytest.fixture
def boundary(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    settings.busy_timeout_ms = 100
    settings.redis_url = 'redis://127.0.0.1:26379'
    settings.redis_key_prefix = 'test:boundaries:' + uuid4().hex + ':'
    migrate(settings)
    redis = Redis.from_url(settings.redis_url)
    keys = set()
    with TestClient(create_app(settings)) as client:
        login = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()
        db = client.app.state.database
        with db.transaction() as s:
            owner = s.scalar(select(users.c.id))
            workspace = create_workspace(s, owner, 'Boundary', 'boundary')
            ids = {'owner':owner}
            for role in ('admin','member','recipient','foreign'):
                uid = ids[role] = str(uuid4())
                s.execute(users.insert().values(id=uid,email=role+'@example.com',name=role,created_at=svc.stamp(),updated_at=svc.stamp()))
                if role in ('admin','member'):
                    s.execute(members.insert().values(id=str(uuid4()),workspace_id=workspace['id'],user_id=uid,role=role,created_at=svc.stamp()))
        def headers(role):
            email = 'dev@workpal.local' if role == 'owner' else role+'@example.com'
            return {'Authorization':'Bearer '+issue_session(ids[role],email,role,settings.auth_secret,3600)}
        def quota(role, email):
            result = InvitationAdmission(client.app.state.redis).keys(ids[role],workspace['id'],email)
            keys.update(result)
            return result
        def snapshot():
            with db.transaction() as s:
                return tuple(s.execute(text('SELECT * FROM '+table)).all() for table in ('workspace_invitation','members','outbox'))
        def invite(email='recipient@example.com', **kwargs):
            with db.transaction() as s:
                return svc.create_invitation(s, {'user_id':owner,'identity_kind':'session'},workspace['id'],email, **kwargs)
        try:
            yield client, db, headers, quota, snapshot, invite, '/api/workspaces/'+workspace['id']+'/members', redis, settings
        finally:
            if keys:
                redis.delete(*keys)
            redis.close()


def test_permissions_and_cookie_csrf(boundary):
    c, db, h, quota, snap, invite, path, redis, _ = boundary
    initial = snap()
    for role, status in (('member',403),('foreign',404)):
        keys = quota(role,'denied@example.com')
        assert c.post(path,headers=h(role),json={'email':'denied@example.com'}).status_code == status
        assert not redis.exists(*keys)
        assert snap() == initial
    assert c.post(path,json={'email':'denied@example.com'}).status_code == 403
    assert snap() == initial
    for role in ('owner','admin'):
        email = role+'-invite@example.com'
        quota(role,email)
        assert c.post(path,headers=h(role),json={'email':email,'unknown':True,'role':None}).status_code == 201
    invitation = invite()
    accept = '/api/invitations/'+invitation['id']+'/accept'
    before = snap()
    assert c.post(accept).status_code == 403
    assert c.post(accept,headers=h('foreign')).status_code == 403
    assert snap() == before
    assert c.post(accept,headers=h('recipient'),content='ignored').status_code == 200


def test_real_redis_429(boundary):
    c, _, h, quota, snap, _, path, redis, _ = boundary
    keys = quota('owner','limited@example.com')
    now = redis.time(); score = now[0]*1000+now[1]/1000
    redis.zadd(keys[0], {str(i):score for i in range(10)})
    before = snap()
    response = c.post(path,headers=h('owner'),json={'email':'limited@example.com'})
    assert response.status_code == 429
    retry = response.json()['retry_after_seconds']
    assert 1 <= retry <= 600
    assert response.json() == {'code':'invitation_rate_limited','error':'too many invitation requests','retry_after_seconds':retry}
    assert response.headers['retry-after'] == str(retry)
    assert response.headers['cache-control'] == 'no-store'
    assert snap() == before
    assert redis.zcard(keys[0]) == 10
    assert not redis.exists(*keys[1:])


def test_unavailable_redis_503(boundary):
    from workpal_backend.infrastructure.redis import RedisResources
    import asyncio
    c, _, h, _, snap, _, path, _, settings = boundary
    settings.redis_url = 'redis://127.0.0.1:1'
    original = c.app.state.redis
    resources = RedisResources(settings)
    c.app.state.redis = resources
    before = snap()
    try:
        response = c.post(path,headers=h('owner'),json={'email':'outage@example.com'})
        assert response.status_code == 503
        assert response.json() == {'code':'invitation_rate_limiter_unavailable','error':'invitation service temporarily unavailable'}
        assert response.headers['retry-after'] == '5'
        assert response.headers['cache-control'] == 'no-store'
        assert snap() == before
    finally:
        c.app.state.redis = original
        asyncio.run(resources.close())


def test_sqlite_write_lock_503(boundary):
    c, _, h, quota, snap, invite, path, _, settings = boundary
    invitation = invite()
    quota('owner','locked@example.com')
    before = snap()
    lock = sqlite3.connect(settings.database_url.removeprefix('sqlite:///'))
    try:
        lock.execute('BEGIN IMMEDIATE')
        assert c.post(path,headers=h('owner'),json={'email':'locked@example.com'}).status_code == 503
        assert c.post('/api/invitations/'+invitation['id']+'/accept',headers=h('recipient')).status_code == 503
    finally:
        lock.rollback()
        lock.close()
    assert snap() == before


def test_expiry_uuid_role_and_decode(boundary, monkeypatch):
    c, _, h, quota, snap, invite, path, _, _ = boundary
    expired = invite(now=datetime.now(timezone.utc)-timedelta(days=8))
    assert c.post('/api/invitations/'+expired['id']+'/accept',headers=h('recipient')).status_code == 410
    valid = invite('foreign@example.com')
    assert c.post('/api/invitations/'+valid['id']+'/accept',headers=h('recipient')).status_code == 403
    assert c.post('/api/invitations/bad/accept',headers=h('recipient')).status_code == 400
    assert c.post('/api/workspaces/bad/members',headers=h('owner'),json={}).status_code == 400
    before = snap()
    for role in ('owner','invalid',3):
        assert c.post(path,headers=h('owner'),json={'email':'bad@example.com','role':role}).status_code == 400
    assert c.post(path,headers=h('owner'),content='null').status_code == 400
    assert snap() == before
    # Acceptance compares strictly before now: exact expiration remains valid.
    fixed = datetime.now(timezone.utc)
    with boundary[1].transaction() as session:
        session.execute(svc.invitations.update().where(svc.invitations.c.id == valid['id']).values(expires_at=svc.stamp(fixed)))
    original_accept = svc.accept_invitation
    monkeypatch.setattr(svc, 'accept_invitation', lambda session, principal, iid: original_accept(session, principal, iid, now=fixed))
    assert c.post('/api/invitations/'+valid['id']+'/accept',headers=h('foreign')).status_code == 200
    quota('owner','decode@example.com')
    assert c.post(path,headers=h('owner'),content='{"email":"decode@example.com","unknown":1} trailing').status_code == 201
