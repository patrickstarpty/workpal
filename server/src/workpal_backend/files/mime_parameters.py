# Copyright 2010 The Go Authors. All rights reserved.
# Adapted from Go mime/mediatype.go; see GO_LICENSE.txt for the BSD license.
"""Go MIME parameters, including duplicate and RFC 2231 continuation rules."""
import re
from urllib.parse import unquote_to_bytes
from workpal_backend.auth.profile_decode import _SPACE, _replace_surrogates, go_trim_space
from workpal_backend.workspaces.decode import go_lower

_SPECIAL = '()<>@,;:\\"/[]?='
_INVALID = 'mime: invalid media parameter'


def _token(value):
    end = 0
    while end < len(value) and 32 < ord(value[end]) < 127 and value[end] not in _SPECIAL:
        end += 1
    return value[:end], value[end:]


def _value(value):
    if not value.startswith('"'):
        return _token(value)
    result = []
    index = 1
    while index < len(value):
        char = value[index]
        if char == '"':
            return ''.join(result), value[index + 1:]
        if char == '\\' and index + 1 < len(value) and value[index + 1] in _SPECIAL:
            result.append(value[index + 1])
            index += 2
            continue
        if char in '\r\n':
            return '', value
        result.append(char)
        index += 1
    return '', value


def _parameter(value):
    rest = value.lstrip(_SPACE)
    if not rest.startswith(';'):
        return '', '', value
    key, rest = _token(rest[1:].lstrip(_SPACE))
    rest = rest.lstrip(_SPACE)
    if not key or not rest.startswith('='):
        return '', '', value
    rest = rest[1:].lstrip(_SPACE)
    result, tail = _value(rest)
    if not result and tail == rest:
        return '', '', value
    return key.lower(), result, tail


def _unescape(value):
    if re.search(r'%(?![0-9a-fA-F]{2})', value):
        return None
    return unquote_to_bytes(value.encode('utf8', 'surrogateescape')).decode('utf8', 'surrogateescape')


def _extended(value):
    parts = value.split("'", 2)
    if len(parts) != 3 or parts[0].lower() not in ('us-ascii', 'utf-8'):
        return None
    return _unescape(parts[2])


def parse_media_type(value):
    base = value.split(';', 1)[0]
    media = go_trim_space(go_lower(_replace_surrogates(base)))
    first, rest = _token(media)
    if not first:
        return '', None, 'mime: no media type'
    if rest:
        if not rest.startswith('/'):
            return '', None, 'mime: expected slash after first token'
        subtype, rest = _token(rest[1:])
        if not subtype:
            return '', None, 'mime: expected token after slash'
        if rest:
            return '', None, 'mime: unexpected content after media subtype'
    params, continuation = {}, {}
    rest = value[len(base):]
    while rest:
        rest = rest.lstrip(_SPACE)
        if not rest:
            break
        key, item, tail = _parameter(rest)
        if not key:
            if go_trim_space(tail) == ';':
                break
            return media, None, _INVALID
        target = continuation.setdefault(key.split('*', 1)[0], {}) if '*' in key else params
        if key in target and target[key] != item:
            return '', None, 'mime: duplicate parameter name'
        target[key] = item
        rest = tail
    for key, pieces in continuation.items():
        if key + '*' in pieces:
            decoded = _extended(pieces[key + '*'])
            if decoded is not None:
                params[key] = decoded
            continue
        assembled = []
        index = 0
        while True:
            part = f'{key}*{index}'
            if part in pieces:
                assembled.append(pieces[part])
            elif part + '*' in pieces:
                raw = pieces[part + '*']
                assembled.append((_extended(raw) if index == 0 else _unescape(raw)) or '')
            else:
                break
            index += 1
        if index:
            # Go concatenates raw bytes before any caller interprets UTF-8.
            params[key] = ''.join(assembled).encode('utf8', 'surrogateescape').decode('utf8', 'surrogateescape')
    return media, params, None
