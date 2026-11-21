"""Interactive authentication. Claims remain on request.state for future renewal."""
from dataclasses import dataclass
from fastapi import Request, HTTPException
from jwt import InvalidTokenError
from .tokens import decode_session, verify_csrf
from .sessions import validate_session

@dataclass(frozen=True)
class Principal:
    user_id: str
    identity_kind: str = 'session'

def require_principal(request: Request) -> Principal:
    settings = request.app.state.settings
    authorization = request.headers.get('authorization')
    cookie = authorization is None
    token = request.cookies.get('workpal_auth') if cookie else (authorization[7:] if authorization.lower().startswith('bearer ') else None)
    try:
        if not settings.dev_auth or not token:
            raise ValueError('missing session')
        with request.app.state.database.transaction() as session:
            claims, user = validate_session(session, settings, token)
        if user is None:
            raise ValueError('missing user')
    except (InvalidTokenError, ValueError):
        raise HTTPException(401, 'Unauthorized')
    if cookie and request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not verify_csrf(request.headers.get('x-csrf-token'), settings.auth_secret, claims['sid'], token):
            raise HTTPException(403, 'Invalid CSRF token')
    request.state.session_claims = claims
    return Principal(user['id'])
