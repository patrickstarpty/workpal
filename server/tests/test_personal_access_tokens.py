import hashlib
import re
import pytest
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate

@pytest.fixture
def client(settings):
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    migrate(settings)
    with TestClient(create_app(settings)) as c:
        login = c.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()
        c.headers['Authorization'] = 'Bearer '+login['token']
        yield c


def test_pat_lifecycle_and_no_raw_secret_storage(client):
    assert client.get('/api/tokens').json() == []
    r = client.post('/api/tokens',json={'name':' CLI '})
    assert r.status_code == 201
    pat = r.json()
    assert re.fullmatch('mul_[0-9a-f]{40}',pat['token'])
    assert pat['name'] == ' CLI '
    assert pat['token_prefix'] == pat['token'][:12]
    assert pat['expires_at'] is None and pat['last_used_at'] is None
    assert client.get('/api/tokens').json() == [{k:v for k,v in pat.items() if k != 'token'}]
    from sqlalchemy import text
    with client.app.state.database.transaction() as session:
        row = dict(session.execute(text('SELECT * FROM personal_access_tokens')).mappings().one())
        assert row['token_hash'] == hashlib.sha256(pat['token'].encode()).hexdigest()
        assert pat['token'] not in row.values()
    headers = {'Authorization':'Bearer '+pat['token']}
    assert client.get('/api/me',headers=headers).status_code == 200
    assert client.post('/api/tokens/current/renew',headers=headers).json() == {'expires_at':'','renewed':False}
    assert client.delete('/api/tokens/'+pat['id']).status_code == 204
    assert client.delete('/api/tokens/'+pat['id']).status_code == 204
    assert client.get('/api/tokens').json() == []
    assert client.get('/api/me',headers=headers).status_code == 401


@pytest.mark.parametrize('body,error', [({},'name is required'),({'name':2},'invalid request body'),({'name':'A','expires_in_days':1.5},'invalid request body'),({'name':'A','expires_in_days':True},'invalid request body')])
def test_pat_validation(client,body,error):
    response=client.post('/api/tokens',json=body)
    assert response.status_code == 400
    assert response.json() == {'error':error}


def test_pat_renew_in_place(client):
    pat=client.post('/api/tokens',json={'name':'renew','expires_in_days':1}).json()
    headers={'Authorization':'Bearer '+pat['token']}
    first=client.post('/api/tokens/current/renew',headers=headers)
    assert first.status_code == 200 and first.json()['renewed'] is True
    second=client.post('/api/tokens/current/renew',headers=headers)
    assert second.json() == {**first.json(),'renewed':False}
    assert client.get('/api/tokens',headers=headers).json()[0]['id'] == pat['id']
    assert client.post('/api/tokens/current/renew').status_code == 400


def test_pat_expired_listed_but_cannot_authenticate(client):
    from sqlalchemy import update
    from workpal_backend.auth.personal_tokens import pats
    pat=client.post('/api/tokens',json={'name':'expired','expires_in_days':1}).json()
    with client.app.state.database.transaction() as session:
        session.execute(update(pats).where(pats.c.id==pat['id']).values(expires_at=1))
    assert client.get('/api/tokens').json()[0]['id']==pat['id']
    assert client.get('/api/me',headers={'Authorization':'Bearer '+pat['token']}).status_code==401


def test_pat_foreign_revoke_and_machine_guard(client):
    from uuid import uuid4
    from sqlalchemy import update
    from workpal_backend.auth.models import users
    from workpal_backend.auth.personal_tokens import pats
    from workpal_backend.auth.dependencies import Principal, require_principal
    pat=client.post('/api/tokens',json={'name':'foreign'}).json()
    other=str(uuid4())
    with client.app.state.database.transaction() as session:
        session.execute(users.insert().values(id=other,email='pat-other@example.com',name='Other',created_at='2026-01-01',updated_at='2026-01-01'))
        session.execute(update(pats).where(pats.c.id==pat['id']).values(user_id=other))
    assert client.delete('/api/tokens/'+pat['id']).status_code==204
    with client.app.state.database.transaction() as session:
        assert session.execute(pats.select().where(pats.c.id==pat['id'])).mappings().one()['revoked'] is False
    for kind in ('task_token','cloud_pat'):
        client.app.dependency_overrides[require_principal]=lambda:Principal(other,kind)
        try:
            assert client.get('/api/tokens').status_code==403
            assert client.post('/api/tokens',json={'name':'escalation'}).status_code==403
        finally:client.app.dependency_overrides.clear()


def test_pat_timestamp_seconds(client):
    pat=client.post('/api/tokens',json={'name':'format','expires_in_days':1}).json()
    for key in ('created_at','expires_at'):
        assert re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',pat[key])


def test_pat_last_used_write_failure_does_not_reject_identity(client):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError
    pat=client.post('/api/tokens',json={'name':'last-used'}).json()
    def fail(conn,cursor,statement,parameters,context,many):
        if statement.startswith('UPDATE personal_access_tokens SET last_used_at'):
            raise OperationalError(statement,parameters,RuntimeError('write failed'))
    engine=client.app.state.database.engine
    event.listen(engine,'before_cursor_execute',fail)
    try:
        assert client.get('/api/me',headers={'Authorization':'Bearer '+pat['token']}).status_code==200
    finally:event.remove(engine,'before_cursor_execute',fail)


def test_pat_cache_ttl_and_revoke(settings, isolated_relay_redis_port):
    from uuid import uuid4
    from redis import Redis
    from sqlalchemy import select
    from workpal_backend.auth.personal_tokens import pats, hash_token
    settings.dev_auth=True
    settings.auth_secret='s'*32
    settings.redis_url=f'redis://127.0.0.1:{isolated_relay_redis_port}'
    settings.redis_key_prefix='test:pat:'+uuid4().hex+':'
    migrate(settings)
    redis=Redis.from_url(settings.redis_url)
    keys=[]
    try:
        with TestClient(create_app(settings)) as c:
            login=c.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()
            c.headers['Authorization']='Bearer '+login['token']
            pat=c.post('/api/tokens',json={'name':'cache','expires_in_days':1}).json()
            key=settings.redis_key_prefix+'mul:auth:pat:'+hash_token(pat['token'])
            keys.append(key)
            headers={'Authorization':'Bearer '+pat['token']}
            assert c.get('/api/me',headers=headers).status_code==200
            assert 0<redis.pttl(key)<=600000
            with c.app.state.database.transaction() as session:
                first=session.scalar(select(pats.c.last_used_at).where(pats.c.id==pat['id']))
            assert c.get('/api/me',headers=headers).status_code==200
            with c.app.state.database.transaction() as session:
                assert session.scalar(select(pats.c.last_used_at).where(pats.c.id==pat['id']))==first
            assert c.delete('/api/tokens/'+pat['id']).status_code==204
            assert redis.exists(key)==0
    finally:
        if keys:redis.delete(*keys)
        redis.close()


def test_pat_concurrent_renewal_has_one_winner(client):
    from concurrent.futures import ThreadPoolExecutor
    pat=client.post('/api/tokens',json={'name':'parallel','expires_in_days':1}).json()
    def renew(_):
        return client.post('/api/tokens/current/renew',headers={'Authorization':'Bearer '+pat['token']})
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses=list(pool.map(renew,range(4)))
    assert [r.status_code for r in responses]==[200]*4
    assert sum(r.json()['renewed'] for r in responses)==1
    assert len({r.json()['expires_at'] for r in responses})==1


def test_pat_is_independent_of_development_login_flag(client):
    pat=client.post('/api/tokens',json={'name':'normal-auth'}).json()
    client.app.state.settings.dev_auth=False
    assert client.get('/api/me',headers={'Authorization':'Bearer '+pat['token']}).status_code==200


@pytest.mark.parametrize('cached',[False,True])
def test_disabled_user_pat_denied_even_on_cache_hit(client, monkeypatch, cached):
    from sqlalchemy import update
    from workpal_backend.auth.models import users
    from workpal_backend.auth.personal_tokens import pats
    from workpal_backend.auth import pat_cache
    disabled='514492f7-b30f-4147-bd33-c0e8ce5d6d4f'
    pat=client.post('/api/tokens',json={'name':'disabled'}).json()
    with client.app.state.database.transaction() as session:
        session.execute(users.insert().values(id=disabled,email='disabled-fixture@example.com',name='Disabled',created_at='2026-01-01',updated_at='2026-01-01'))
        session.execute(update(pats).where(pats.c.id==pat['id']).values(user_id=disabled))
    if cached:monkeypatch.setattr(pat_cache,'get',lambda *args:disabled)
    response=client.get('/api/me',headers={'Authorization':'Bearer '+pat['token']})
    assert response.status_code==403
    assert response.json()=={'error':'account disabled'}
    with client.app.state.database.transaction() as session:
        assert session.execute(pats.select().where(pats.c.id==pat['id'])).mappings().one()['last_used_at'] is None


def test_invalid_pat_middleware_wire_response(client):
    response=client.get('/api/me',headers={'Authorization':'Bearer mul_invalid'})
    assert response.status_code==401
    assert response.content==b'{"error":"invalid token"}\n'
    assert response.headers['content-type']=='text/plain; charset=utf-8'
    assert response.headers['x-content-type-options']=='nosniff'


@pytest.mark.parametrize('operation,error',[('SELECT','failed to look up token'),('UPDATE','failed to renew token')])
def test_pat_renew_database_failure_messages(client,operation,error):
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError
    from workpal_backend.auth.dependencies import Principal,require_principal
    uid=client.get('/api/me').json()['id']
    pat=client.post('/api/tokens',json={'name':'db-error','expires_in_days':1}).json()
    client.app.dependency_overrides[require_principal]=lambda:Principal(uid)
    def fail(conn,cursor,statement,parameters,context,many):
        if statement.startswith(operation) and 'personal_access_tokens' in statement:
            raise OperationalError(statement,parameters,RuntimeError('injected'))
    engine=client.app.state.database.engine
    event.listen(engine,'before_cursor_execute',fail)
    try:
        response=client.post('/api/tokens/current/renew',headers={'Authorization':'Bearer '+pat['token']})
        assert response.status_code==500
        assert response.json()=={'error':error}
    finally:
        event.remove(engine,'before_cursor_execute',fail)
        client.app.dependency_overrides.clear()


def test_pat_handler_json_wire_format(client):
    empty=client.get('/api/tokens')
    assert empty.content==b'[]\n'
    error=client.post('/api/tokens',json={})
    assert error.content==b'{"error":"name is required"}\n'
    created=client.post('/api/tokens',json={'name':'<A>&\u2028\u2029'})
    assert b'\\u003cA\\u003e\\u0026\\u2028\\u2029' in created.content
    assert created.content.endswith(b'\n')
    assert created.headers['content-type']=='application/json'
    assert int(created.headers['content-length'])==len(created.content)


def test_pat_name_nul_rejected_by_storage_contract(client):
    response=client.post('/api/tokens',json={'name':'bad\u0000name'})
    assert response.status_code==500
    assert response.json()=={'error':'failed to create token'}
    assert client.get('/api/tokens').json()==[]
