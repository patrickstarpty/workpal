"""Exact questionnaire numbers, isolated from event JSON serialization.

PostgreSQL docs: datatype-json.html rejects U+0000 and unmatched surrogate
pairs; datatype-numeric.html limits numeric to 131072 integral/16383 fractional
 digits. These are source-based limits, not an executed PostgreSQL oracle.
"""
import json
from decimal import Decimal
from sqlalchemy.types import TypeDecorator, Text
from starlette.responses import Response


def validate(value):
    if isinstance(value, str):
        if '\0' in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValueError('invalid JSONB text')
    elif isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError('nonfinite number')
        _, digits, exponent = value.as_tuple()
        if max(len(digits) + exponent, 0) > 131072 or max(-exponent, 0) > 16383:
            raise ValueError('numeric out of range')
    elif isinstance(value, dict):
        for key, item in value.items():
            validate(key)
            validate(item)
    elif isinstance(value, list):
        for item in value:
            validate(item)


def dumps(value):
    # Decimal's scientific notation keeps exponent encoding bounded.
    if isinstance(value, Decimal):
        validate(value)
        return str(value)
    if isinstance(value, dict):
        return '{' + ','.join(json.dumps(k) + ':' + dumps(v) for k, v in value.items()) + '}'
    if isinstance(value, list):
        return '[' + ','.join(dumps(v) for v in value) + ']'
    return json.dumps(value, ensure_ascii=True, allow_nan=False)


class QuestionnaireJSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        validate(value)
        # BLOB binding avoids SQLite JSON-column NUMERIC affinity rounding scalars.
        return dumps(value).encode("utf-8")

    def process_result_value(self, value, dialect):
        if isinstance(value, (int, float)):
            return value  # Legacy SQLite numeric-affinity scalar; never rewrite on read.
        return json.loads(value, parse_float=Decimal, parse_int=Decimal) if value is not None else None


def user_response(value):
    def public_user(row):
        return {key: item for key, item in row.items()
                if key not in {'cloud_waitlist_email', 'cloud_waitlist_reason'}}

    if 'user' in value:
        value = {**value, 'user': public_user(value['user'])}
    else:
        value = public_user(value)
    return Response(dumps(value), media_type='application/json')
