"""Ordered Go-style string decoding; stdlib mailbox parsing approximation."""
import json
import re
from email.headerregistry import HeaderRegistry
from email._header_value_parser import get_address
from email.errors import NonASCIILocalPartDefect
from .profile_decode import _Object, _replace_surrogates, _invalid_constant, go_trim_space


def decode_waitlist(raw):
    try:
        source = _replace_surrogates(raw.decode('utf-8', errors='surrogateescape'))
        obj, _ = json.JSONDecoder(object_pairs_hook=_Object, parse_constant=_invalid_constant).raw_decode(source, re.match(r'[ \t\r\n]*', source).end())
        if obj is None:
            obj = _Object()
        if not isinstance(obj, _Object):
            raise ValueError()
        fields = {'email': '', 'reason': ''}
        for key, value in obj:
            folded = ''.join(c.upper() if 'a' <= c <= 'z' else
                             'S' if c == '\u017f' else
                             'K' if c == '\u212a' else c for c in key)
            key = next((field for field in fields if field.upper() == folded), None)
            if key not in fields:
                continue
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError()
                fields[key] = _replace_surrogates(value)
    except (ValueError, RecursionError) as exc:
        raise ValueError('invalid request body') from exc
    # Go uses simple Unicode lower casing (not Python's expanding dotted I).
    email = ''.join('i' if c == '\u0130' else c.lower() for c in go_trim_space(fields['email']))
    if not email:
        raise ValueError('email is required')
    if len(email.encode()) > 254:
        raise ValueError('email is too long')
    try:
        # Parse one address, retaining remainder (HeaderRegistry parses a list).
        _, remainder = get_address(email)
        header = HeaderRegistry()('to', email)
        defects = [d for d in header.defects if not isinstance(d, NonASCIILocalPartDefect)]
        addresses = header.addresses
        if remainder or defects or len(addresses) != 1 or not addresses[0].username or not addresses[0].domain or any(c in email for c in '\r\n'):
            raise ValueError()
    except Exception as exc:
        raise ValueError('email is invalid') from exc
    reason = go_trim_space(fields['reason'])
    if len(reason.encode()) > 500:
        raise ValueError('reason is too long')
    return email, reason or None
