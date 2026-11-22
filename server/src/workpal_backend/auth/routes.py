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
from .token_source import extract_token

router = APIRouter()
COOKIES = ('workpal_auth', 'workpal_csrf_session', 'workpal_csrf')

def supported(request, email):
    if not request.app.state.settings.dev_auth or email.strip().lower() not in ('dev@workpal.local', 'workpal@fwd.com'):
        raise HTTPException(501, 'Email delivery is not supported')

@router.get('/api/config')
def config(request: Request):
    return dict(development_auth=request.app.state.settings.dev_auth,
        cdn_domain='', allow_signup=False, daemon_setup_target='self_host',
        workspace_creation_disabled=request.app.state.settings.disable_workspace_creation,
        posthog_key='', posthog_host='', analytics_environment='', feature_flags={'issue_assignment_without_runtime': True},
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
    from jwt import InvalidTokenError
    from .tokens import decode_auth_jwt
    from . import session_renewal as renewal
    settings=request.app.state.settings
    raw,from_cookie=extract_token(request)
    try:
        claims=decode_auth_jwt(raw,settings.auth_secret)
    except (InvalidTokenError,ValueError):
        raise HTTPException(400,'only interactive sessions can be refreshed')
    if claims['sub'] != principal.user_id:
        raise HTTPException(401,'token does not belong to caller')
    result={'expires_at':renewal.format_expiry(renewal.expiry(claims)),'renewed':False,
        'check_again_in_seconds':min(max(settings.auth_token_ttl//10,5),604800,settings.auth_token_ttl//4)}
    if not renewal.due(claims,settings):return result
    try:
        token,expires=renewal.renew_claims(claims,settings)
    except HTTPException:
        raise
    except Exception:
        return result
    if from_cookie:
        try:renewal.set_cookies(response,token,settings)
        except Exception:return result
    else:
        result={'token':token,**result}
    result.update(expires_at=renewal.format_expiry(expires),renewed=True)
    return result
