"""Persist validated local interest inside the caller's transaction."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from .models import users


def join_waitlist(session, user_id, email, reason):
    """Accept already normalized values; never commit the caller's transaction."""
    try:
        connection = session.connection()
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        with session.begin_nested():
            row = session.execute(update(users).where(users.c.id == user_id).values(
                cloud_waitlist_email=email, cloud_waitlist_reason=reason,
                updated_at=datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
            ).returning(*users.c)).mappings().one_or_none()
            if row is None:
                raise HTTPException(500, 'failed to join waitlist')
            return dict(row)
    except SQLAlchemyError as exc:
        # Let the outer transaction classify retryable SQLite contention.
        if isinstance(exc, OperationalError) and any(word in str(exc).lower() for word in ('locked', 'busy')):
            raise
        raise HTTPException(500, 'failed to join waitlist') from exc
