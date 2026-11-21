"""Manual development sign-in and public deployment capabilities."""
from .json_codec import user_response
import hashlib
import hmac
import secrets
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit
from sqlalchemy.exc import SQLAlchemyError
from fastapi import APIRouter, Depends, Request, Response, HTTPException
from .schemas import SendCode, VerifyCode
from .dependencies import Principal, require_principal
from .service import get_or_create_development_user, get_user
from .tokens import issue_session, decode_session, csrf_token

router = APIRouter()
COOKIES = ('workpal_auth', 'workpal_csrf_session', 'workpal_csrf')

def supported(request, email):
    if not request.app.state.settings.dev_auth or email.strip().lower() != 'dev@workpal.local':
        raise HTTPException(501, 'Email delivery is not supported')

@router.get('/api/config')
def config(request: Request):
    return dict(development_auth=request.app.state.settings.dev_auth,
        cdn_domain='', allow_signup=False, daemon_setup_target='self_host',
        workspace_creation_disabled=request.app.state.settings.disable_workspace_creation,
        posthog_key='', posthog_host='', analytics_environment='', feature_flags={},
        vcs_integration_available=False, theme_store_enabled=False,
        local_worktree_supported=False, agent_conversation_starters_supported=False,
        webhook_payload_conditions_supported=False, issue_create_properties_supported=False,
        comment_delete_keep_replies_supported=False, issue_batch_ops_supported=False)

@router.post('/auth/send-code')
def send_code(body: SendCode, request: Request):
    if not body.email.strip():
        raise HTTPException(400, 'email is required')
    if not request.app.state.settings.dev_auth:
        supported(request, body.email)
    from .rate_limit import check
    check(request, 'send', body.email)
    supported(request, body.email)
    return {'message': 'Verification code sent'}

@router.post('/auth/verify-code')
def verify_code(body: VerifyCode, request: Request, response: Response):
    if not body.email.strip() or not body.code.strip():
        raise HTTPException(400, 'email and code are required')
    if not request.app.state.settings.dev_auth:
        supported(request, body.email)
    from .rate_limit import check
    check(request, 'verify')
    supported(request, body.email)
    if body.code.strip() != '888888':
        raise HTTPException(400, 'invalid or expired code')
    settings = request.app.state.settings
    with request.app.state.database.transaction() as session:
        user = get_or_create_development_user(session, body.email)
    token = issue_session(user['id'], user['email'], user['name'], settings.auth_secret, settings.auth_token_ttl)
    claims = decode_session(token, settings.auth_secret)
    nonce = secrets.token_bytes(16)
    legacy = nonce.hex() + '.' + hmac.new(token.encode(), nonce, hashlib.sha256).hexdigest()
    values = (token, csrf_token(settings.auth_secret, claims['sid']), legacy)
    for name, value in zip(COOKIES, values):
        response.set_cookie(name, value, httponly=name == 'workpal_auth', secure=urlsplit(settings.frontend_origin).scheme == 'https', samesite='strict', path='/', domain=settings.cookie_domain or None, max_age=settings.auth_token_ttl, expires=datetime.now(timezone.utc) + timedelta(seconds=settings.auth_token_ttl))
    result = user_response({'token': token, 'user': user})
    result.raw_headers.extend((k, v) for k, v in response.raw_headers if k.lower() == b'set-cookie')
    return result

@router.post('/auth/logout')
def logout(response: Response, request: Request):
    from jwt import InvalidTokenError
    from .sessions import revoke_session
    authorization = request.headers.get('authorization')
    token = request.cookies.get('workpal_auth') if authorization is None else (authorization[7:] if authorization.lower().startswith('bearer ') else None)
    if token and request.app.state.settings.dev_auth:
        try:
            with request.app.state.database.transaction() as session:
                revoke_session(session, request.app.state.settings, token)
        except (InvalidTokenError, ValueError):
            pass

    for name in COOKIES:
        response.set_cookie(name, '', max_age=-1, expires=datetime(1970,1,1,tzinfo=timezone.utc), path='/', domain=request.app.state.settings.cookie_domain or None, samesite='strict', httponly=name == 'workpal_auth', secure=urlsplit(request.app.state.settings.frontend_origin).scheme == 'https')
    return {'message': 'logged out'}

@router.post('/auth/google')
def google():
    raise HTTPException(501, 'Google authentication is not supported')

@router.get('/api/me')
def me(request: Request, principal: Principal = Depends(require_principal)):
    try:
        with request.app.state.database.transaction() as session:
            user = get_user(session, principal.user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(500, 'failed to load user') from exc
    if user is None:
        raise HTTPException(401, 'user not found')
    return user_response(user)

@router.post('/api/auth/refresh')
def refresh(request: Request, response: Response, principal: Principal = Depends(require_principal)):
    import time
    settings = request.app.state.settings
    from .sessions import validate_session
    from jwt import InvalidTokenError
    authorization = request.headers.get('authorization')
    token = request.cookies.get('workpal_auth') if authorization is None else (authorization[7:] if authorization.lower().startswith('bearer ') else None)
    try:
        with request.app.state.database.transaction() as session:
            claims, _ = validate_session(session, settings, token)
    except (InvalidTokenError, ValueError):
        raise HTTPException(401, 'Unauthorized')
    now = int(time.time())
    renewed = 0 < claims['exp'] - now <= settings.auth_token_ttl / 2
    result = {'expires_at': datetime.fromtimestamp(claims['exp'], timezone.utc).isoformat().replace('+00:00', 'Z'), 'renewed': renewed, 'check_again_in_seconds': min(max(settings.auth_token_ttl // 10, 5), 604800, settings.auth_token_ttl // 4)}
    if renewed:
        token = issue_session(claims['sub'], claims['email'], claims['name'], settings.auth_secret, settings.auth_token_ttl, sid=claims['sid'])
        result['expires_at'] = datetime.fromtimestamp(now + settings.auth_token_ttl, timezone.utc).isoformat().replace('+00:00', 'Z')
        if request.headers.get('authorization') is not None:
            result['token'] = token
        else:
            for name, value in [('workpal_auth', token), ('workpal_csrf_session', csrf_token(settings.auth_secret, claims['sid']))]:
                response.set_cookie(name, value, httponly=name == 'workpal_auth', secure=urlsplit(settings.frontend_origin).scheme == 'https', samesite='strict', path='/', domain=settings.cookie_domain or None, max_age=settings.auth_token_ttl, expires=datetime.now(timezone.utc)+timedelta(seconds=settings.auth_token_ttl))
    return result
