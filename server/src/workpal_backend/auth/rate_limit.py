"""Main-database, first-attempt anchored fixed windows using wall-clock seconds.

Each attempt owns a short transaction committed before authentication/Redis work,
so failed authentication still counts. Schema belongs exclusively to Alembic.
"""
import hashlib
import math
import time
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from workpal_backend.infrastructure.database import DatabaseBusy


def consume(database, key, limit, window, *, now=None):
    now = time.time() if now is None else now
    key = hashlib.sha256(key.encode()).hexdigest()
    denied_until = None
    try:
        with database.transaction() as session:
            # The first statement takes SQLite's writer lock before reading counts.
            # Indexed, bounded batches amortize retention work across attempts.
            session.execute(text('DELETE FROM auth_limits WHERE key IN (SELECT key FROM auth_limits WHERE expires <= :now LIMIT 256)'), {'now': now})
            row = session.execute(text('SELECT expires,count FROM auth_limits WHERE key=:key'), {'key': key}).first()
            if row and row.expires > now and row.count >= limit:
                denied_until = row.expires
            else:
                session.execute(text('''INSERT INTO auth_limits(key,expires,count) VALUES (:key,:expires,1)
                    ON CONFLICT(key) DO UPDATE SET
                    count=CASE WHEN auth_limits.expires <= :now THEN 1 ELSE auth_limits.count+1 END,
                    expires=CASE WHEN auth_limits.expires <= :now THEN :expires ELSE auth_limits.expires END'''),
                    {'key': key, 'expires': now+window, 'now': now})
    except (SQLAlchemyError, DatabaseBusy) as exc:
        raise HTTPException(503, 'Authentication limiter unavailable', headers={'Retry-After': '1'}) from exc
    if denied_until is not None:
        raise HTTPException(429, 'Too many requests', headers={'Retry-After': str(max(1, math.ceil(denied_until-now)))})


def check(request, operation, email=None):
    database = request.app.state.database
    ip = request.client.host if request.client else 'unknown'
    consume(database, operation+':ip:'+ip, 5 if operation == 'send' else 20, 60)
    if email is not None:
        consume(database, 'send:email:'+email.strip().lower(), 1, 60)
