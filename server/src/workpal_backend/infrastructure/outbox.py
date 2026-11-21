"""Transactional outbox. All APIs use caller transactions; commit claims before I/O.

Delivery is at least once. Tokens fence acknowledgements, not external delivery.
Envelope follows internal/events/bus.go; eventID is a server-owned extension.
"""
import json
import re
import time
from uuid import uuid4
from sqlalchemy import Table, Column, MetaData, String, Text, Float, Integer, select, update, insert, or_, and_, literal_column

outbox = Table('outbox', MetaData(),
    Column('event_id', String, primary_key=True), Column('envelope', Text, nullable=False),
    Column('state', String, nullable=False), Column('claim_token', String),
    Column('claim_until', Float), Column('attempts', Integer, nullable=False),
    Column('retry_at', Float, nullable=False), Column('last_error', Text))


def append_event(session, event):
    """Append only; duplicate explicit IDs raise IntegrityError, even if identical."""
    if not session.in_transaction():
        raise ValueError('append_event requires an existing transaction')
    allowed = {'eventID', 'type', 'workspaceID', 'payload', 'actorType', 'actorID',
               'taskID', 'chatSessionID', 'chatSessionOwnerID', 'memberPrivateUserID'}
    if not isinstance(event, dict) or set(event) - allowed:
        raise ValueError('Invalid event envelope')
    for key in ('workspaceID', 'type'):
        if not isinstance(event.get(key), str) or not event[key].strip():
            raise ValueError(f'{key} required')
    if not re.fullmatch(r'[A-Za-z0-9_-]+:[A-Za-z0-9_:-]+', event['type']):
        raise ValueError('Invalid event type')
    if 'payload' not in event:
        raise ValueError('payload required')
    for key in allowed - {'payload', 'type', 'workspaceID'}:
        if key in event and (not isinstance(event[key], str) or not event[key].strip()):
            raise ValueError(f'Invalid {key}')
    if event.get('actorType') not in (None, 'member', 'agent', 'system'):
        raise ValueError('Invalid actorType')
    event_id = event.get('eventID', str(uuid4()))
    envelope = json.dumps(dict(event, eventID=event_id), allow_nan=False, sort_keys=True)
    session.execute(insert(outbox).values(event_id=event_id, envelope=envelope,
        state='pending', attempts=0, retry_at=0))
    return event_id


def claim_batch(session, *, now=None, limit=100, lease_seconds=30):
    """Claim at most the FIFO head; limit is an upper bound, not a batch size.

    SQLite serializes writers, so the normal table's durable rowid records
    committed insertion order. Select the oldest unfinished row BEFORE testing
    eligibility: a retry delay or live lease must block all newer snapshots.
    This deliberately trades global head-of-line blocking for single-worker
    ordering. Commit and close the transaction before network I/O.
    """
    if not 1 <= limit <= 100 or not 1 <= lease_seconds <= 300:
        raise ValueError('Invalid claim bounds')
    now = time.time() if now is None else now
    eligible = or_(and_(outbox.c.state == 'pending', outbox.c.retry_at <= now),
                   and_(outbox.c.state == 'claimed', outbox.c.claim_until <= now))
    ids = (select(outbox.c.event_id).where(outbox.c.state != 'delivered')
           .order_by(literal_column('outbox.rowid')).limit(1))
    rows = session.execute(update(outbox).where(outbox.c.event_id.in_(ids), eligible).values(
        state='claimed', claim_token=str(uuid4()), claim_until=now + lease_seconds,
        attempts=outbox.c.attempts + 1).returning(outbox)).mappings().all()
    return [dict(row) for row in rows]


def _owned(event_id, token, now):
    return and_(outbox.c.event_id == event_id, outbox.c.state == 'claimed',
                outbox.c.claim_token == token, outbox.c.claim_until > now)


def ack(session, event_id, token, *, now=None):
    """Return False for expired, replaced or completed claims."""
    now = time.time() if now is None else now
    return session.execute(update(outbox).where(_owned(event_id, token, now)).values(
        state='delivered', claim_token=None, claim_until=None)).rowcount == 1


def retry(session, event_id, token, error, *, now=None, delay_seconds=30):
    """Conditionally release a live claim with bounded backoff and error text."""
    if not 0 <= delay_seconds <= 86400:
        raise ValueError('Invalid retry delay')
    now = time.time() if now is None else now
    return session.execute(update(outbox).where(_owned(event_id, token, now)).values(
        state='pending', claim_token=None, claim_until=None, retry_at=now + delay_seconds,
        last_error=str(error)[:2048])).rowcount == 1
