"""Caller-owned atomic onboarding completion; analytics intentionally disabled."""
import json
import re
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import update, func
from .models import users
from .profile_decode import _Object, _replace_surrogates, _invalid_constant


def decode_completion(raw):
    source = _replace_surrogates(raw.decode('utf-8', errors='surrogateescape'))
    if not source.strip(' \t\r\n'):
        return {}
    try:
        value, _ = json.JSONDecoder(object_pairs_hook=_Object, parse_constant=_invalid_constant).raw_decode(source, re.match(r'[ \t\r\n]*', source).end())
        if value is None:
            return {}
        if not isinstance(value, _Object):
            raise ValueError()
        result = {}
        for key, item in value:
            folded = ''.join(c.upper() if 'a' <= c <= 'z' else 'S' if c == '\u017f' else 'K' if c == '\u212a' else c for c in key)
            if folded in ('COMPLETION_PATH', 'WORKSPACE_ID'):
                if item is not None:
                    if not isinstance(item, str):
                        raise ValueError()
                    result[folded.lower()] = _replace_surrogates(item)
        return result
    except (ValueError, RecursionError) as exc:
        raise HTTPException(400, 'invalid request body') from exc


def complete_onboarding(session, user_id):
    connection = session.connection()
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
    with session.begin_nested():
        now = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
        row = session.execute(update(users).where(users.c.id == user_id).values(
            onboarded_at=func.coalesce(users.c.onboarded_at, now), updated_at=now
        ).returning(*users.c)).mappings().one_or_none()
        if row is None:
            raise HTTPException(500, 'failed to complete onboarding')
        return dict(row)
