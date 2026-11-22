"""Persisted PAT lifecycle derived from personal_access_token.go and its SQL."""
import hashlib
import secrets
import time
from datetime import datetime, timezone
from uuid import uuid4, UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import Table, Column, String, Text, Float, Boolean, MetaData, select, update
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from .dependencies import require_principal
from workpal_backend.infrastructure.go_response import GoJSONResponse
from workpal_backend.infrastructure.database import DatabaseBusy
from workpal_backend.workspaces.decode import _decode

pats = Table('personal_access_tokens',MetaData(),
    Column('id',String,primary_key=True), Column('user_id',String), Column('name',Text),
    Column('token_hash',Text),Column('token_prefix',Text),Column('expires_at',Float),
    Column('last_used_at',Float),Column('revoked',Boolean),Column('created_at',Float))


def timestamp(value):
    return datetime.fromtimestamp(value,timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z') if value is not None else None


def public(row):
    return dict(id=row['id'],name=row['name'],token_prefix=row['token_prefix'],
        expires_at=timestamp(row['expires_at']),last_used_at=timestamp(row['last_used_at']),created_at=timestamp(row['created_at']))


def hash_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def lookup(session, raw, now=None):
    now = time.time() if now is None else now
    return session.execute(select(pats).where(pats.c.token_hash==hash_token(raw),pats.c.revoked.is_(False),
        (pats.c.expires_at.is_(None)) | (pats.c.expires_at > now))).mappings().one_or_none()


def human(principal=Depends(require_principal)):
    if principal.identity_kind in ('task_token','cloud_pat'):
        raise HTTPException(403,'this endpoint is only available to human actors')
    return principal

router=APIRouter(prefix='/api/tokens',default_response_class=GoJSONResponse)


def transaction(request, error, operation):
    try:
        with request.app.state.database.transaction() as session:
            return operation(session)
    except (SQLAlchemyError, DatabaseBusy) as exc:
        raise HTTPException(500,error) from exc


@router.get('')
def list_tokens(request: Request, principal=Depends(human)):
    return transaction(request,'failed to list tokens',lambda session: [public(row) for row in session.execute(
        select(pats).where(pats.c.user_id==principal.user_id,pats.c.revoked.is_(False)).order_by(pats.c.created_at.desc())).mappings()])


@router.post('',status_code=201)
async def create_token(request: Request, principal=Depends(human)):
    try:
        body=_decode(await request.body(),{'name':'string','expires_in_days':'pointer_int'},{'name':'','expires_in_days':None})
    except ValueError as exc:
        raise HTTPException(400,'invalid request body') from exc
    if body['name']=='': raise HTTPException(400,'name is required')
    try: raw='mul_'+secrets.token_hex(20)
    except Exception as exc: raise HTTPException(500,'failed to generate token') from exc
    now=time.time()
    days=body['expires_in_days']
    # Go time.Duration arithmetic wraps signed int64 nanoseconds.
    delta=((days*86400000000000+2**63)%2**64-2**63)/1e9 if days is not None and days>0 else None
    row=dict(id=str(uuid4()),user_id=principal.user_id,name=body['name'],token_hash=hash_token(raw),
        token_prefix=raw[:12],expires_at=now+delta if delta is not None else None,last_used_at=None,revoked=False,created_at=now)
    def save(session):
        session.execute(pats.insert().values(**row))
        return dict(public(row),token=raw)
    return await run_in_threadpool(transaction,request,'failed to create token',save)


@router.delete('/{token_id}',status_code=204)
def revoke(token_id: str, request: Request, principal=Depends(human)):
    try: token_id=str(UUID(token_id))
    except ValueError: raise HTTPException(400,'invalid token id')
    token_hash=transaction(request,'failed to revoke token',lambda session:session.execute(update(pats).where(
        pats.c.id==token_id,pats.c.user_id==principal.user_id).values(revoked=True).returning(pats.c.token_hash)).scalar_one_or_none())
    if token_hash:
        from .pat_cache import invalidate
        invalidate(request.app.state.settings, token_hash)
    return Response(status_code=204)


@router.post('/current/renew')
def renew(request: Request, principal=Depends(human)):
    header=request.headers.get('authorization','')
    if not header.startswith('Bearer mul_'):
        raise HTTPException(400,'only personal access tokens can be renewed')
    raw=header[7:]
    def operation(session):
        now=time.time()
        try:
            row=lookup(session,raw,now)
        except (SQLAlchemyError, DatabaseBusy) as exc:
            raise HTTPException(500,'failed to look up token') from exc
        if row is None: raise HTTPException(401,'token is no longer valid')
        if row['user_id']!=principal.user_id: raise HTTPException(401,'token does not belong to caller')
        expiry=row['expires_at']
        if expiry is None: return dict(expires_at='',renewed=False)
        if expiry-now>7*86400: return dict(expires_at=timestamp(expiry),renewed=False)
        new_expiry=now+90*86400
        changed=session.execute(update(pats).where(pats.c.id==row['id'],pats.c.revoked.is_(False),
            pats.c.expires_at>now,pats.c.expires_at<=now+7*86400).values(expires_at=new_expiry).returning(pats.c.expires_at)).scalar_one_or_none()
        if changed is not None: return dict(expires_at=timestamp(changed),renewed=True)
        try:
            current=lookup(session,raw)
        except (SQLAlchemyError, DatabaseBusy) as exc:
            raise HTTPException(401,'token is no longer valid') from exc
        if current is None: raise HTTPException(401,'token is no longer valid')
        return dict(expires_at=timestamp(current['expires_at']) or '',renewed=False)
    return transaction(request,'failed to renew token',operation)
