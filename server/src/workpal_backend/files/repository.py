"""Caller-owned transactions; tokens fence all upload and cleanup transitions.

Times are UTC epoch seconds. Staging identity is immutable, independent of the
rotating cleanup token. Callers commit reservation before touching the store and
revalidate authorization/targets in the same transaction as finalize_ready.
"""
import secrets
import time
from uuid import uuid4
from sqlalchemy import select, update, delete
from .models import upload_intent as t

class StaleLease(RuntimeError):
    pass

def _now(now): return time.time() if now is None else now

def _duration(value):
    if not 0 < value <= 3600: raise ValueError('lease must be between 0 and 3600 seconds')
    return value

def reserve_intent(session, principal, target, key, lease=None, *, now=None, lease_seconds=60):
    now = _now(now); token = lease or secrets.token_hex(16)
    row = dict(id=str(uuid4()), storage_key=key, staging_key=token,
               owner_type=principal.get('owner_type', 'member'), owner_id=principal['owner_id'],
               workspace_id=principal.get('workspace_id'), target_json=dict(target),
               state='pending', lease_token=token, lease_expires_at=now+_duration(lease_seconds),
               next_attempt_at=now, created_at=now, updated_at=now)
    session.execute(t.insert().values(**row))
    return row

def _upload_guard(id, token, now):
    return (t.c.id==id, t.c.state=='pending', t.c.lease_token==token, t.c.lease_expires_at>now)

def _checked(session, statement):
    if session.execute(statement).rowcount != 1: raise StaleLease('Upload lease is no longer current')

def renew_lease(session, id, token, *, now=None, lease_seconds=60):
    now = _now(now)
    _checked(session, update(t).where(*_upload_guard(id, token, now)).values(
        lease_expires_at=now+_duration(lease_seconds), updated_at=now))

def finalize_ready(session, id, token, metadata, *, now=None):
    now = _now(now)
    allowed = {'attachment_id','size_bytes','sha256','content_type','filename','width','height'}
    if set(metadata)-allowed: raise ValueError('Unknown upload metadata')
    _checked(session, update(t).where(*_upload_guard(id, token, now)).values(
        **metadata, state='ready', updated_at=now))

def mark_deleting(session, id, principal, *, now=None):
    now = _now(now)
    _checked(session, update(t).where(t.c.id==id, t.c.state=='ready',
        t.c.owner_id==principal['owner_id'], t.c.owner_type==principal.get('owner_type','member')).values(
        state='deleting', lease_token=secrets.token_hex(16), lease_expires_at=now,
        next_attempt_at=now, updated_at=now))

def claim_expired(session, now=None, limit=100, *, lease_seconds=60):
    now = _now(now); duration = _duration(lease_seconds)
    if not 0 < limit <= 1000: raise ValueError('limit must be 1..1000')
    eligible = (t.c.state.in_(['pending','failed','deleting']), t.c.lease_expires_at<=now, t.c.next_attempt_at<=now)
    rows = session.execute(select(t).where(*eligible).order_by(t.c.created_at,t.c.id).limit(limit)).mappings().all()
    claims = []
    for row in rows:
        token = secrets.token_hex(16)
        result = session.execute(update(t).where(*eligible, t.c.id==row['id'], t.c.lease_token==row['lease_token']).values(
            state='deleting', lease_token=token, lease_expires_at=now+duration, updated_at=now))
        if result.rowcount: claims.append(dict(row, state='deleting', lease_token=token, lease_expires_at=now+duration))
    return claims

def _claim_guard(claim, now):
    return (t.c.id==claim['id'], t.c.state=='deleting', t.c.lease_token==claim['lease_token'], t.c.lease_expires_at>now)

def complete_cleanup(session, claim, *, now=None):
    _checked(session, delete(t).where(*_claim_guard(claim, _now(now))))

def fail_cleanup(session, claim, error, *, now=None, retry_seconds=60):
    now = _now(now)
    _checked(session, update(t).where(*_claim_guard(claim, now)).values(
        state='failed', last_error=str(error)[:2000], next_attempt_at=now+_duration(retry_seconds),
        lease_expires_at=now, updated_at=now))
