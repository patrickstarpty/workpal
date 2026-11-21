"""Profile persistence within a caller-owned transaction; no event producer."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import update
from fastapi import HTTPException
from .models import users
from .service import get_user
from .profile_decode import go_trim_space


def update_profile(session, user_id, patch, stage):
    # SQLite legacy transaction mode does not BEGIN on SELECT or SAVEPOINT.
    # Establish the real outer transaction before releasing a nested savepoint.
    connection = session.connection()
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
    # A savepoint protects reusable callers that catch validation/update errors.
    with session.begin_nested():
        stage[0] = 'load'
        current = get_user(session, user_id)
        if current is None:
            raise HTTPException(404, 'user not found')
        values = {'name': current['name']}
        for field in ('name', 'avatar_url', 'language', 'profile_description', 'timezone'):
            if patch.get(field) is None:
                continue
            value = go_trim_space(patch[field])
            if field == 'name' and not value:
                raise HTTPException(400, 'name is required')
            if field == 'avatar_url' and value and value != go_trim_space(current['avatar_url'] or ''):
                raise HTTPException(501, 'Avatar updates are not supported')
            if field == 'language' and value not in ('en','zh-Hans','zh-Hant','ko','ja','fr','es','ru'):
                raise HTTPException(400, 'unsupported language')
            if field == 'profile_description' and len(value) > 2000:
                raise HTTPException(400, 'profile_description exceeds 2000 characters')
            if field == 'timezone':
                if value and value not in ('UTC', 'Local'):
                    try:
                        ZoneInfo(value)
                    except (ZoneInfoNotFoundError, ValueError):
                        raise HTTPException(400, 'invalid timezone')
                value = value or None
            values[field] = value
        values['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
        stage[0] = 'update'
        row = session.execute(update(users).where(users.c.id == user_id).values(**values).returning(*users.c)).mappings().one_or_none()
        if row is None:
            raise HTTPException(500, 'failed to update user')
        return dict(row)
