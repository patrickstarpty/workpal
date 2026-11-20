"""Pure query input semantics; returned values confer no authorization."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo
import hashlib
import json
import re
from workpal.contracts import DomainError

_MAX = 2**63 - 1

@dataclass(frozen=True)
class QueryWindow:
    start: datetime
    end: datetime

@dataclass(frozen=True)
class QueryFilters:
    level: str | None = None
    text: str | None = None

@dataclass(frozen=True)
class QueryRequest:
    source_id: int
    service: int
    capability: Literal['search_logs']
    time_window: QueryWindow | None
    timezone: str | None
    filters: QueryFilters
    cursor: str | None
    key: str
    input_hash: str

def _invalid():
    raise DomainError('invalid_input', 'Invalid query request.', status=400)

def _tree(v, seen):
    t = type(v)
    if t is str:
        if any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in v):
            _invalid()
    elif t in (dict, list):
        if id(v) in seen:
            _invalid()
        seen.add(id(v))
        if t is dict:
            for k, x in v.items():
                if type(k) is not str:
                    _invalid()
                _tree(k, seen)
                _tree(x, seen)
        else:
            for x in v:
                _tree(x, seen)
        seen.remove(id(v))
    elif t not in (int, bool, type(None)):
        _invalid()

def _string(v, limit):
    if type(v) is not str or not 1 <= len(v) <= limit:
        _invalid()
    return v

def _time(v):
    _string(v, 64)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)', v, flags=re.ASCII) or v.endswith('-00:00'):
        _invalid()
    return datetime.fromisoformat(v.replace('Z', '+00:00')).astimezone(timezone.utc)

def _stamp(v):
    return f'{v.year:04d}-{v.month:02d}-{v.day:02d}T{v.hour:02d}:{v.minute:02d}:{v.second:02d}.{v.microsecond:06d}Z'

def _json(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')

def normalize_query_request(value: dict) -> QueryRequest:
    try:
        _tree(value, set())
        if type(value) is not dict or set(value) - {'source_id','service','capability','key','time_window','timezone','filters','cursor'} or not {'source_id','service','capability','key'} <= set(value):
            _invalid()
        for k in ('source_id', 'service'):
            if type(value[k]) is not int or not 1 <= value[k] <= _MAX:
                _invalid()
        if value['capability'] != 'search_logs':
            _invalid()
        key = _string(value['key'], 200)
        if not key.strip():
            _invalid()
        w = value.get('time_window')
        window = None
        if w is not None:
            if type(w) is not dict or set(w) != {'start','end'}:
                _invalid()
            window = QueryWindow(_time(w['start']), _time(w['end']))
            if window.start >= window.end:
                _invalid()
        tz = value.get('timezone')
        if tz is not None:
            _string(tz, 100)
            if '\\' in tz or any(p in ('', '.', '..') for p in tz.split('/')):
                _invalid()
            ZoneInfo(tz)
        f = value.get('filters', {})
        if type(f) is not dict or set(f) - {'level','text'}:
            _invalid()
        if 'level' in f and f['level'] not in ('debug','info','warn','error'):
            _invalid()
        if 'text' in f:
            _string(f['text'], 1024)
        cursor = value.get('cursor')
        if cursor is not None:
            _string(cursor, 2048)
        payload = dict(source_id=value['source_id'], service=value['service'], capability='search_logs', time_window=None if window is None else dict(start=_stamp(window.start), end=_stamp(window.end)), timezone=tz, filters=dict(f), cursor=cursor)
        if len(_json(dict(payload, key=key))) > 16384:
            _invalid()
        digest = hashlib.sha256(b'query-v1\0' + _json(payload)).hexdigest()
        return QueryRequest(value['source_id'], value['service'], 'search_logs', window, tz, QueryFilters(f.get('level'), f.get('text')), cursor, key, digest)
    except DomainError:
        raise
    except (ValueError, TypeError, OverflowError, KeyError, RecursionError):
        _invalid()

def _pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            _invalid()
        result[k] = v
    return result

def parse_query_request(body: bytes) -> QueryRequest:
    if type(body) is not bytes or len(body) > 16384:
        _invalid()
    try:
        value = json.loads(body.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=lambda _: _invalid())
    except (ValueError, UnicodeError, RecursionError):
        _invalid()
    return normalize_query_request(value)
