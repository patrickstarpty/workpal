"""Development user persistence; transaction ownership belongs to the caller."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from .models import users


def get_user(session: Session, id: str) -> dict | None:
    row = session.execute(select(users).where(users.c.id == id)).mappings().one_or_none()
    return dict(row) if row is not None else None


def get_or_create_development_user(session: Session, email: str) -> dict:
    email = email.strip().lower()
    if email != 'dev@workpal.local':
        raise ValueError('Only dev@workpal.local is supported for development authentication')
    now = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    session.execute(
        insert(users).values(id=str(uuid4()), email=email, name='Development User',
                             created_at=now, updated_at=now)
        .on_conflict_do_nothing(index_elements=[users.c.email])
    )
    return dict(session.execute(select(users).where(users.c.email == email)).mappings().one())
