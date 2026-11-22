"""Onboarding replacement in a caller-owned transaction, without analytics."""
import json
from decimal import Decimal
from .json_codec import validate
import re
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import update
from .models import users
from .profile_decode import _Object, _replace_surrogates, _invalid_constant, ProfileDecodeError


def decode_onboarding(raw):
    source = _replace_surrogates(raw.decode('utf-8', errors='surrogateescape'))
    try:
        value, _ = json.JSONDecoder(object_pairs_hook=_Object, parse_float=Decimal, parse_int=Decimal, parse_constant=_invalid_constant).raw_decode(
            source, re.match(r'[ \t\r\n]*', source).end())
        if value is None:
            return {}
        if not isinstance(value, _Object):
            raise ProfileDecodeError()
        def materialize(item):
            if isinstance(item, _Object):
                result = {}
                for k, v in item:
                    validate(k)
                    result[k] = materialize(v)
                return result
            if isinstance(item, list):
                return [materialize(v) for v in item]
            validate(item)
            return item
        patch = {}
        for key, item in value:
            # Same ASCII SimpleFold cycle used by the profile decoder.
            folded = ''.join(c.upper() if 'a' <= c <= 'z' else
                             'S' if c == '\u017f' else 'K' if c == '\u212a' else c for c in key)
            if folded == 'QUESTIONNAIRE':
                patch['questionnaire'] = materialize(item)
        validate(patch)
        return patch
    except (ValueError, RecursionError) as exc:
        raise ProfileDecodeError('invalid request body') from exc


def update_onboarding(session, user_id, patch):
    connection = session.connection()
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
    with session.begin_nested():
        values = {'updated_at': datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')}
        if patch.get('questionnaire') is not None:
            values['onboarding_questionnaire'] = patch['questionnaire']
        row = session.execute(update(users).where(users.c.id == user_id).values(**values).returning(*users.c)).mappings().one_or_none()
        if row is None:
            raise HTTPException(500, 'failed to update onboarding')
        return dict(row)
