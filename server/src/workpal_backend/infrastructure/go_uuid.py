"""Canonical UUIDs using the frozen pgx v5.11.0 pgtype.UUID Scan grammar."""
import re
from uuid import UUID


def parse_uuid(value):
    if not isinstance(value, str):
        raise ValueError('invalid UUID')
    raw = value.encode('utf-8')
    if len(raw) == 36:
        raw = raw[:8] + raw[9:13] + raw[14:18] + raw[19:23] + raw[24:]
    if not re.fullmatch(rb'[0-9a-fA-F]{32}', raw):
        raise ValueError('invalid UUID')
    return str(UUID(hex=raw.decode('ascii')))
