"""Go jwt/v5 default parser and middleware Auth claim requirements."""
import pytest
import jwt
from workpal_backend.auth import tokens
SECRET='s'*64

@pytest.mark.parametrize('algorithm',['HS256','HS384','HS512'])
@pytest.mark.parametrize('claims',[{'sub':'user'}, {'sub':'user','iat':9999999999}, {'sub':'user','iat':'unused','exp':0}, {'sub':'user','email':7,'sid':None,'name':False}])
def test_go_auth_accepts_optional_claims(algorithm,claims):
    assert tokens.decode_auth_jwt(jwt.encode(claims,SECRET,algorithm=algorithm),SECRET,now=100)==claims

@pytest.mark.parametrize('claims',[{'sub':'user','exp':100},{'sub':'user','exp':'200'}, {'sub':'user','exp':None}, {'sub':'user','nbf':101}, {'sub':'user','nbf':'99'}, {'sub':'user','extra':float('nan')}])
def test_go_auth_rejects_invalid_registered_or_json_values(claims):
    with pytest.raises(jwt.InvalidTokenError):
        tokens.decode_auth_jwt(jwt.encode(claims,SECRET,algorithm='HS256'),SECRET,now=100)

@pytest.mark.parametrize('claims',[{}, {'sub':None},{'sub':7},{'sub':' \t'}])
def test_go_auth_requires_nonblank_string_subject(claims):
    with pytest.raises(tokens.InvalidAuthClaims):
        tokens.decode_auth_jwt(jwt.encode(claims,SECRET,algorithm='HS256'),SECRET,now=100)


def test_csrf_sid_verifies_signature_without_claim_validation():
    raw=jwt.encode({'sid':'old','exp':1,'nbf':9999},SECRET,algorithm='HS384')
    assert tokens.signed_session_id(raw,SECRET)=='old'
    assert tokens.signed_session_id(raw, 'x'*64)==''
