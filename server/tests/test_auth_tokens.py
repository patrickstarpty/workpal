import hashlib
import hmac

import jwt
import pytest

from workpal_backend.auth.tokens import issue_session, decode_session, csrf_token, verify_csrf

SECRET = 's' * 32
CLAIMS = dict(sub='u', email='u@example.com', name='User', sid='session', iat=100, exp=200)


def test_roundtrip_and_renewal():
    token = issue_session('u', 'u@example.com', 'User', SECRET, 100, now=100)
    claims = decode_session(token, SECRET, now=101)
    assert claims['sub'] == 'u'
    assert claims['email'] == 'u@example.com'
    assert claims['name'] == 'User'
    assert claims['iat'] == 100 and claims['exp'] == 200
    csrf = csrf_token(SECRET, claims['sid'])
    renewed = issue_session('u', 'u@example.com', 'User', SECRET, 100, now=150, sid=claims['sid'])
    assert renewed != token
    assert decode_session(renewed, SECRET, now=151)['sid'] == claims['sid']
    assert verify_csrf(csrf, SECRET, claims['sid'])
    assert not verify_csrf(csrf, SECRET, 'other')


@pytest.mark.parametrize('claim', CLAIMS)
def test_required_claims(claim):
    claims = CLAIMS.copy()
    del claims[claim]
    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_session(jwt.encode(claims, SECRET, algorithm='HS256'), SECRET, now=110)


@pytest.mark.parametrize('claims,error', [({**CLAIMS, 'iat': 120}, jwt.ImmatureSignatureError), ({**CLAIMS, 'iat': 'bad'}, jwt.InvalidIssuedAtError), ({**CLAIMS, 'exp': 110}, jwt.ExpiredSignatureError)])
def test_times(claims, error):
    with pytest.raises(error):
        decode_session(jwt.encode(claims, SECRET, algorithm='HS256'), SECRET, now=110)


def test_invalid_tokens():
    token = jwt.encode(CLAIMS, SECRET, algorithm='HS256')
    for value in [token + 'x', 'mul_' + token, 'mat_' + token, 'mcn_' + token, jwt.encode(CLAIMS, '', algorithm='none'), jwt.encode(CLAIMS, SECRET * 2, algorithm='HS512')]:
        with pytest.raises(jwt.InvalidTokenError):
            decode_session(value, SECRET, now=110)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_session(token, 'x' * 32, now=110)


def test_secret_length():
    with pytest.raises(ValueError):
        issue_session('u', 'e', 'n', 'short', 100)
    with pytest.raises(ValueError):
        decode_session('x', 'short')


def test_not_before_is_enforced():
    for nbf in (120, 'bad', True):
        token = jwt.encode({**CLAIMS, 'nbf': nbf}, SECRET, algorithm='HS256')
        with pytest.raises(jwt.InvalidTokenError):
            decode_session(token, SECRET, now=110)
    token = jwt.encode({**CLAIMS, 'nbf': 110}, SECRET, algorithm='HS256')
    assert decode_session(token, SECRET, now=110)['sub'] == 'u'


def test_go_csrf_and_legacy():
    nonce = bytes(range(16))
    for key, message, legacy in [(SECRET, b'session\0' + nonce, None), ('jwt-token', nonce, 'jwt-token')]:
        value = nonce.hex() + '.' + hmac.new(key.encode(), message, hashlib.sha256).hexdigest()
        assert verify_csrf(value, SECRET, 'session', legacy_token=legacy)
    for value in ['', '.', 'zz.00', '00.zz', '00.00', None, 'a.b.c']:
        assert not verify_csrf(value, SECRET, 'session')
