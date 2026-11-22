"""Shared HTTP/WS session checks. Caller owns transaction and error handling."""
import time
from sqlalchemy import Table, Column, MetaData, String, Float, select, delete, func
from sqlalchemy.dialects.sqlite import insert
from jwt import InvalidTokenError
from .tokens import decode_session
from .service import get_user

revocations = Table('session_revocations', MetaData(),
    Column('sid', String, primary_key=True), Column('expires_at', Float, nullable=False))


def validate_session(session, settings, token):
    """Return (verified claims, persisted user); reject revoked/disabled sessions.

    Database failures propagate: transports must fail closed, never send content.
    WS callers must repeat this authoritative check before each content batch and
    arrange their own bounded idle checks/expiry deadline.
    """
    if not settings.dev_auth:
        raise InvalidTokenError('sessions disabled')
    claims = decode_session(token, settings.auth_secret)
    if session.execute(select(revocations.c.sid).where(revocations.c.sid == claims['sid'])).first():
        raise InvalidTokenError('session revoked')
    user = get_user(session, claims['sub'])
    if user is None:
        raise InvalidTokenError('missing user')
    return claims, user


def revoke_session(session, settings, token):
    """Persist signed sid; retain through every possible outstanding renewal.

    Renewal can extend expiry by a full configured TTL. The retention horizon
    therefore covers that TTL from revocation, even for a copied older token.
    Cleanup deletes at most 100 expired records in the same transaction.
    """
    claims = decode_session(token, settings.auth_secret)
    now = time.time()
    horizon = max(claims['exp'], now + settings.auth_token_ttl)
    session.execute(delete(revocations).where(revocations.c.sid.in_(
        select(revocations.c.sid).where(revocations.c.expires_at <= now).limit(100))))
    statement = insert(revocations).values(sid=claims['sid'], expires_at=horizon)
    session.execute(statement.on_conflict_do_update(index_elements=['sid'],
        set_={'expires_at': func.max(revocations.c.expires_at, horizon)}))
