"""Stateless interactive-session renewal from Go auth/session.go."""
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlsplit
import jwt
from fastapi import HTTPException, Response
from .tokens import csrf_token, signed_session_id
from .disabled_users import reject_disabled


def expiry(claims):
    value=claims.get('exp')
    return int(value) if isinstance(value,(int,float)) and value else None


def due(claims, settings):
    expires=expiry(claims)
    return expires is not None and 0 < expires-time.time() <= settings.auth_token_ttl/2


def format_expiry(value):
    return datetime.fromtimestamp(value,timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z') if value is not None else ''


def renew_claims(claims, settings):
    sub=claims.get('sub')
    if not isinstance(sub,str) or not sub:raise ValueError('not a session')
    email=claims.get('email')
    reject_disabled(sub,email if isinstance(email,str) else '')
    sid=claims.get('sid')
    if not isinstance(sid,str) or not sid:sid=secrets.token_hex(16)
    now=int(time.time())
    result=dict(sub=sub,exp=now+settings.auth_token_ttl,iat=now,sid=sid)
    for field in ('email','name'):
        if isinstance(claims.get(field),str) and claims[field]:result[field]=claims[field]
    return jwt.encode(result,settings.auth_secret,algorithm='HS256'),result['exp']


def set_cookies(response, token, settings):
    expires=datetime.now(timezone.utc)+timedelta(seconds=settings.auth_token_ttl)
    def set_cookie(name,value):
        response.set_cookie(name,value,httponly=name=='workpal_auth',secure=urlsplit(settings.frontend_origin).scheme.lower()=='https',
            samesite='strict',path='/',domain=settings.cookie_domain or None,max_age=settings.auth_token_ttl,expires=expires)
    set_cookie('workpal_auth',token)
    nonce=secrets.token_bytes(16)
    legacy=nonce.hex()+'.'+hmac.new(token.encode(),nonce,hashlib.sha256).hexdigest()
    set_cookie('workpal_csrf',legacy)
    sid=signed_session_id(token,settings.auth_secret)
    if sid:set_cookie('workpal_csrf_session',csrf_token(settings.auth_secret,sid))


def prepare_cookie_renewal(request, claims, from_cookie):
    settings=request.app.state.settings
    if not from_cookie or request.method not in ('GET','HEAD','OPTIONS') or not due(claims,settings):return
    response=Response()
    try:
        token,_=renew_claims(claims,settings)
        set_cookies(response,token,settings)
    except Exception:
        # Go treats automatic renewal failures as nonfatal; existing auth stands.
        pass
    request.state.renewal_cookie_headers=[(k,v) for k,v in response.raw_headers if k==b'set-cookie']
