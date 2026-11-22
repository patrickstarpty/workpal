"""Development user persistence; transaction ownership belongs to the caller."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from .models import users


def get_user(session: Session, id: str) -> dict | None:
    row = session.execute(select(users).where(users.c.id == id)).mappings().one_or_none()
    return dict(row) if row is not None else None


def get_or_create_development_user(session: Session, email: str) -> dict:
    email = email.strip().lower()
    if email not in ('dev@workpal.local', 'workpal@fwd.com'):
        raise ValueError('Only the local demonstration account is supported')
    existing = session.execute(select(users).where(users.c.email == 'workpal@fwd.com')).mappings().one_or_none()
    if existing is not None:
        return dict(existing)
    if email == 'workpal@fwd.com':
        # Keep the same identity so workspace memberships and records survive.
        session.execute(update(users).where(users.c.email == 'dev@workpal.local').values(email=email))
    now = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    session.execute(
        insert(users).values(id=str(uuid4()), email=email, name='Development User',
                             created_at=now, updated_at=now)
        .on_conflict_do_nothing(index_elements=[users.c.email])
    )
    return dict(session.execute(select(users).where(users.c.email == email)).mappings().one())
