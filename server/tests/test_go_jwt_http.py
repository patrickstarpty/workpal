import time
import jwt
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.auth.dependencies import require_principal
from workpal_backend.auth.tokens import csrf_token

@pytest.fixture
def client(settings):
    settings.auth_secret='s'*64
    app=create_app(settings)
    @app.get('/fixture/identity')
    @app.post('/fixture/identity')
    def identity(principal=Depends(require_principal)):
        return {'id':principal.user_id}
    with TestClient(app) as c:yield c

@pytest.mark.parametrize('algorithm',['HS256','HS384','HS512'])
def test_http_jwt_independent_of_dev_login_and_database(client,algorithm):
    token=jwt.encode({'sub':'not-a-database-user','iat':9999999999},'s'*64,algorithm=algorithm)
    response=client.get('/fixture/identity',headers={'Authorization':'Bearer '+token})
    assert response.status_code==200
    assert response.json()=={'id':'not-a-database-user'}


def test_cookie_csrf_is_checked_before_auth_and_expired_sid_still_verifies(client):
    token=jwt.encode({'sub':'user','sid':'session','exp':1},'s'*64,algorithm='HS256')
    client.cookies.set('workpal_auth',token)
    response=client.post('/fixture/identity')
    assert response.status_code==403
    assert response.json()=={'error':'CSRF validation failed'}
    response=client.post('/fixture/identity',headers={'X-CSRF-Token':csrf_token('s'*64,'session')})
    assert response.status_code==401
    assert response.json()=={'error':'invalid token'}


def test_http_missing_and_invalid_subject_errors(client):
    assert client.get('/fixture/identity').json()=={'error':'missing authorization'}
    token=jwt.encode({'sub':' \t'},'s'*64,algorithm='HS256')
    response=client.get('/fixture/identity',headers={'Authorization':'Bearer '+token})
    assert response.status_code==401
    assert response.json()=={'error':'invalid claims'}


def test_cookie_without_exp_does_not_attempt_renewal(client):
    client.cookies.set('workpal_auth',jwt.encode({'sub':'user'},'s'*64,algorithm='HS256'))
    response=client.get('/fixture/identity')
    assert response.status_code==200
    assert not response.headers.get_list('set-cookie')


def test_refresh_legacy_optional_identity_and_logout_stateless(client):
    token=jwt.encode({'sub':'user','exp':int(time.time())+20,'custom':'discard'},'s'*64,algorithm='HS384')
    response=client.post('/api/auth/refresh',headers={'Authorization':'Bearer '+token})
    assert response.status_code==200
    assert response.json()['renewed'] is True
    claims=jwt.decode(response.json()['token'],'s'*64,algorithms=['HS256'])
    assert set(claims)=={'sub','sid','iat','exp'}
    assert claims['sid']
    assert client.post('/auth/logout',headers={'Authorization':'Bearer '+token}).status_code==200
    assert client.get('/fixture/identity',headers={'Authorization':'Bearer '+token}).status_code==200


def test_refresh_no_expiration_no_database(client):
    token=jwt.encode({'sub':'user'},'s'*64,algorithm='HS256')
    response=client.post('/api/auth/refresh',headers={'Authorization':'Bearer '+token})
    assert response.status_code==200
    assert response.json()=={'expires_at':'','renewed':False,'check_again_in_seconds':259200}


def test_automatic_renewal_occurs_before_handler_even_on_error(client):
    from fastapi import HTTPException,Request
    @client.app.get('/fixture/fails')
    def fail(request:Request, principal=Depends(require_principal)):
        assert request.state.session_claims['sub']=='user'
        raise HTTPException(404,'missing fixture')
    client.cookies.set('workpal_auth',jwt.encode({'sub':'user','exp':int(time.time())+20},'s'*64,algorithm='HS256'))
    response=client.get('/fixture/fails')
    assert response.status_code==404
    assert len(response.headers.get_list('set-cookie'))==3


def test_signing_failure_is_nonfatal(client,monkeypatch):
    from workpal_backend.auth import session_renewal
    token=jwt.encode({'sub':'user','exp':int(time.time())+20},'s'*64,algorithm='HS256')
    def fail(*args):raise RuntimeError('signer failed')
    monkeypatch.setattr(session_renewal,'renew_claims',fail)
    response=client.post('/api/auth/refresh',headers={'Authorization':'Bearer '+token})
    assert response.status_code==200 and response.json()['renewed'] is False
    client.cookies.set('workpal_auth',token)
    response=client.get('/fixture/identity')
    assert response.status_code==200 and not response.headers.get_list('set-cookie')
