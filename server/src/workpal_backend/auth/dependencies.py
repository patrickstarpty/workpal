"""Interactive authentication. Claims remain on request.state for future renewal."""
from dataclasses import dataclass
from fastapi import Request, HTTPException
from jwt import InvalidTokenError
from .tokens import decode_session, verify_csrf, decode_auth_jwt, signed_session_id, InvalidAuthClaims
from .sessions import validate_session
from .token_source import extract_token
from .disabled_users import reject_disabled
from .errors import AuthenticationError
from workpal_backend.infrastructure.database import DatabaseBusy

@dataclass(frozen=True)
class Principal:
    user_id: str
    identity_kind: str = 'session'

def require_principal(request: Request) -> Principal:
    settings = request.app.state.settings
    token, cookie = extract_token(request)
    if not token:
        raise AuthenticationError(401, 'missing authorization')
    if cookie and request.method not in ('GET','HEAD','OPTIONS'):
        sid = signed_session_id(token, settings.auth_secret)
        if not verify_csrf(request.headers.get('x-csrf-token'), settings.auth_secret, sid, token):
            raise AuthenticationError(403, 'CSRF validation failed')
    if token.startswith('mcn_'):
        from .cloud_pat import CloudPATVerifier, CloudPATInvalid, CloudPATUnavailable
        from .models import users
        from sqlalchemy import select
        from workpal_backend.infrastructure.go_uuid import parse_uuid
        def lookup_owner(owner):
            try:
                owner = parse_uuid(owner)
            except ValueError:
                return False
            with request.app.state.database.transaction() as session:
                return session.execute(select(users.c.id).where(users.c.id == owner)).first() is not None
        try:
            identity = CloudPATVerifier(settings.cloud_url, settings=settings).verify(token, lookup_owner)
        except CloudPATInvalid as exc:
            raise AuthenticationError(401, 'invalid token') from exc
        except CloudPATUnavailable as exc:
            raise AuthenticationError(503, 'cloud pat verifier unavailable') from exc
        reject_disabled(identity['o'])
        return Principal(identity['o'], 'cloud_pat')
    principal, claims = authenticate_token(settings, request.app.state.database, token)
    if claims is not None:
        request.state.session_claims = claims
        request.state.auth_from_cookie = cookie
        from .session_renewal import prepare_cookie_renewal
        prepare_cookie_renewal(request, claims, cookie)
    return principal


def authenticate_token(settings, database, token):
    """Authenticate once without HTTP cookie renewal or transport concerns."""
    if token.startswith('mul_'):
        from .personal_tokens import lookup, pats, hash_token
        from . import pat_cache
        from sqlalchemy import update
        from sqlalchemy.exc import SQLAlchemyError
        import time
        token_hash = hash_token(token)
        cached = pat_cache.get(settings, token_hash)
        if cached:
            reject_disabled(cached)
            return Principal(cached), None
        try:
            with database.transaction() as session:
                row = lookup(session, token)
                if row is None:
                    raise AuthenticationError(401, 'invalid token')
                user_id = row['user_id']
        except (SQLAlchemyError, DatabaseBusy) as exc:
            raise AuthenticationError(401, 'invalid token') from exc
        reject_disabled(user_id)
        pat_cache.put(settings, token_hash, user_id, row['expires_at'])
        try:
            with database.transaction() as session:
                session.execute(update(pats).where(pats.c.id == row['id']).values(last_used_at=time.time()))
        except (SQLAlchemyError, DatabaseBusy):
            pass
        return Principal(user_id), None
    try:
        claims = decode_auth_jwt(token, settings.auth_secret)
    except InvalidAuthClaims as exc:
        raise AuthenticationError(401, 'invalid claims') from exc
    except (InvalidTokenError, ValueError) as exc:
        raise AuthenticationError(401, 'invalid token') from exc
    email = claims.get('email')
    reject_disabled(claims['sub'], email if isinstance(email,str) else '')
    return Principal(claims['sub']), claims
