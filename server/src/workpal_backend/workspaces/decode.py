"""Ordered decoding of workspace request structs from handler/workspace.go."""
import json
import math
import re
from workpal_backend.auth.profile_decode import _Object, _replace_surrogates, _invalid_constant


class _Number(str):
    pass


def _any(value):
    if isinstance(value, _Object):
        return {_replace_surrogates(k): _any(v) for k, v in value}
    if isinstance(value, list):
        return [_any(v) for v in value]
    if isinstance(value, _Number):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError()
        return result
    return _replace_surrogates(value) if isinstance(value, str) else value


def _decode(raw, types, defaults):
    fields = defaults.copy()
    try:
        source = _replace_surrogates(raw.decode('utf-8', errors='surrogateescape'))
        obj, _ = json.JSONDecoder(object_pairs_hook=_Object, parse_constant=_invalid_constant,
            parse_int=_Number, parse_float=_Number).raw_decode(source, re.match(r'[ \t\r\n]*', source).end())
        if obj is None:
            return fields
        if not isinstance(obj, _Object):
            raise ValueError()
        for key, value in obj:
            folded = ''.join(c.upper() if 'a' <= c <= 'z' else
                             'S' if c == '\u017f' else 'K' if c == '\u212a' else c for c in key)
            field = next((name for name in types if name.upper() == folded), None)
            if field is None:
                continue
            kind = types[field]
            if kind == 'any':
                fields[field] = _any(value)
            elif value is None:
                if kind != 'string':
                    fields[field] = None
            elif kind in ('string', 'pointer_string') and type(value) is str:
                fields[field] = _replace_surrogates(value)
            elif kind == 'pointer_int' and isinstance(value, _Number) and re.fullmatch(r'-?[0-9]+', value) and -(2**63) <= int(value) < 2**63:
                fields[field] = int(value)
            elif kind == 'pointer_bool' and type(value) is bool:
                fields[field] = value
            else:
                raise ValueError()
        return fields
    except (ValueError, RecursionError, OverflowError) as exc:
        raise ValueError('invalid request body') from exc


def decode_create(raw):
    fields = dict(name='', slug='', description=None, context=None, issue_prefix=None)
    return _decode(raw, {k: 'string' if k in ('name','slug') else 'pointer_string' for k in fields}, fields)


def decode_update(raw):
    fields = dict.fromkeys(('name','description','context','issue_prefix','avatar_url','settings','repos'))
    return _decode(raw, {k: 'any' if k in ('settings','repos') else 'pointer_string' for k in fields}, fields)


def decode_pin(raw):
    return _decode(raw, {'pinned':'pointer_bool'}, {'pinned':None})['pinned']


def go_lower(value):
    return ''.join('i' if c == '\u0130' else c.lower() for c in value)


def go_upper(value):
    def upper(c):
        result = c.upper()
        if len(result) == 1:
            return result
        title = c.title()
        return title if len(title) == 1 else c
    return ''.join(upper(c) for c in value)
