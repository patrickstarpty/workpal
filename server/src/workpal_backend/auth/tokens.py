"""HS256 interactive sessions and Go-compatible CSRF bindings.

Legacy local session issuance requires 32-byte keys; Go CSRF accepts the configured
UTF-8 secret without a length restriction. Times are Unix seconds.
Invalid tokens raise PyJWT InvalidTokenError subclasses; invalid configuration
or issuance arguments raise ValueError. CSRF verification returns False for
malformed values. Callers retain sid when renewing a session.
"""
import hashlib
import hmac
import math
import re
import secrets
import time

import jwt


def _key(secret: str | bytes) -> bytes:
    key = secret.encode() if isinstance(secret, str) else secret
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError('signing secret must contain at least 32 bytes')
    return key


def _time(now):
    value = time.time() if now is None else now
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('now must be finite Unix seconds')
    return value


def issue_session(user_id, email, name, secret, ttl_seconds, now=None, sid=None) -> str:
    """Issue a session, generating a random sid unless one is retained."""
    key = _key(secret)
    issued = int(_time(now))
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
        raise ValueError('ttl_seconds must be a positive integer')
    sid = secrets.token_hex(16) if sid is None else sid
    claims = dict(sub=user_id, email=email, name=name, sid=sid, iat=issued, exp=issued + ttl_seconds)
    if any(not isinstance(claims[k], str) or not claims[k] for k in ('sub', 'email', 'name', 'sid')):
        raise ValueError('identity claims and sid must be nonempty strings')
    return jwt.encode(claims, key, algorithm='HS256')


def decode_session(token, secret, now=None) -> dict:
    """Verify signature, required claims and timestamps at the supplied time.

    Raises MissingRequiredClaimError, InvalidSignatureError, InvalidAlgorithmError,
    InvalidIssuedAtError, ImmatureSignatureError, ExpiredSignatureError or other
    InvalidTokenError subclasses. No legacy session without sid is accepted.
    """
    key = _key(secret)
    current = _time(now)
    if not isinstance(token, str) or token.startswith(('mul_', 'mat_', 'mcn_')):
        raise jwt.InvalidTokenError('not an interactive session')
    claims = jwt.decode(token, key, algorithms=['HS256'], options={
        'require': ['sub', 'email', 'name', 'sid', 'iat', 'exp'],
        'verify_iat': False, 'verify_exp': False, 'verify_nbf': False,
        'verify_aud': False,
    })
    for field in ('sub', 'email', 'name', 'sid'):
        if not isinstance(claims[field], str) or not claims[field]:
            raise jwt.InvalidTokenError(f'{field} must be a nonempty string')
    for field, error in [('iat', jwt.InvalidIssuedAtError), ('exp', jwt.DecodeError)]:
        value = claims[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise error(f'{field} must be finite numeric seconds')
    if claims['iat'] > current:
        raise jwt.ImmatureSignatureError('session issued in the future')
    if 'nbf' in claims:
        not_before = claims['nbf']
        if isinstance(not_before, bool) or not isinstance(not_before, (int, float)) or not math.isfinite(not_before):
            raise jwt.DecodeError('nbf must be finite numeric seconds')
        if not_before > current:
            raise jwt.ImmatureSignatureError('session is not yet valid')
    if claims['exp'] <= current:
        raise jwt.ExpiredSignatureError('session expired')
    return claims


def _csrf_key(secret):
    key = secret.encode() if isinstance(secret, str) else secret
    if not isinstance(key, bytes):
        raise ValueError('signing secret must be a string or bytes')
    return key


def csrf_token(secret, sid) -> str:
    """Generate hex(16 random bytes).hex(session HMAC-SHA256)."""
    key = _csrf_key(secret)
    nonce = secrets.token_bytes(16)
    signature = hmac.new(key, sid.encode() + b'\0' + nonce, hashlib.sha256).hexdigest()
    return nonce.hex() + '.' + signature


def verify_csrf(value, secret, sid, legacy_token=None) -> bool:
    """Accept session binding or optional legacy JWT-key binding, in constant time.

    As in Go, verification accepts any even-length hex nonce; issuance uses 16
    bytes. Invalid signing configuration raises ValueError.
    """
    key = _csrf_key(secret)
    if not isinstance(value, str) or not re.fullmatch(r'(?:[0-9a-fA-F]{2})*\.[0-9a-fA-F]{64}', value):
        return False
    nonce_hex, signature_hex = value.split('.')
    nonce, signature = bytes.fromhex(nonce_hex), bytes.fromhex(signature_hex)
    valid = False
    if isinstance(sid, str) and sid:
        valid = hmac.compare_digest(signature, hmac.digest(key, sid.encode() + b'\0' + nonce, 'sha256'))
    if isinstance(legacy_token, str) and legacy_token:
        valid = hmac.compare_digest(signature, hmac.digest(legacy_token.encode(), nonce, 'sha256')) or valid
    return valid


class InvalidAuthClaims(jwt.InvalidTokenError):
    """Validly signed token lacking the subject required by Go Auth."""


def _go_signed_claims(token, secret):
    if not isinstance(token, str) or not isinstance(secret, (str, bytes)):
        raise jwt.InvalidTokenError('invalid token')
    claims = jwt.decode(token, secret, algorithms=['HS256','HS384','HS512'], options={
        'verify_exp':False,'verify_nbf':False,'verify_iat':False,'verify_aud':False,
        'verify_iss':False,'verify_sub':False,'verify_jti':False})
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise jwt.InvalidTokenError('invalid JSON number')
        if isinstance(value, dict):
            for item in value.values(): finite(item)
        elif isinstance(value, list):
            for item in value: finite(item)
    finite(claims)
    return claims


def decode_auth_jwt(token, secret, now=None):
    """Go middleware.Auth: HMAC signature, optional exp/nbf, required subject.

    This intentionally differs from the old local-only decode_session parser.
    Go's default parser does not require sid/email/name/iat/exp, or validate iat.
    """
    claims = _go_signed_claims(token, secret)
    current = _time(now)
    for field in ('exp','nbf'):
        if field not in claims:
            continue
        value = claims[field]
        if isinstance(value,bool) or not isinstance(value,(int,float)):
            raise jwt.InvalidTokenError('invalid numeric date')
        if value == 0:
            continue
        instant = math.floor(value)  # jwt.TimePrecision defaults to seconds.
        if field == 'exp' and current >= instant:
            raise jwt.ExpiredSignatureError('token expired')
        if field == 'nbf' and current < instant:
            raise jwt.ImmatureSignatureError('token not yet valid')
    from .profile_decode import go_trim_space
    if not isinstance(claims.get('sub'),str) or not go_trim_space(claims['sub']):
        raise InvalidAuthClaims('invalid claims')
    return claims


def signed_session_id(token, secret):
    try:
        sid = _go_signed_claims(token,secret).get('sid')
        return sid if isinstance(sid,str) else ''
    except (jwt.InvalidTokenError, ValueError, TypeError):
        return ''
