"""Go URL.Query().Get and Request.Cookie selection for WS authentication."""
import re
from urllib.parse import unquote_to_bytes


def query_value(raw, name):
    key = name.encode('utf-8')
    for part in raw.split(b'&'):
        if b';' in part:
            continue
        candidate, _, value = part.partition(b'=')
        if re.search(br'%(?![0-9a-fA-F]{2})', candidate + b'&' + value):
            continue
        if unquote_to_bytes(candidate.replace(b'+', b' ')) == key:
            return unquote_to_bytes(value.replace(b'+', b' ')).decode('utf-8', errors='surrogateescape')
    return ''


def first_cookie(lines, name):
    # Pinned Go1.26 default; a rejected Cookie header is indistinguishable
    # from an absent cookie in Request.Cookie.
    if sum(line.count(';') + 1 for line in lines) > 3000:
        return None
    for line in lines:
        for part in line.strip(' \t').split(';'):
            candidate, _, value = part.strip(' \t').partition('=')
            if candidate.strip(' \t') != name:
                continue
            if len(value) > 1 and value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            if all(32 <= ord(char) < 127 and char not in '";\\' for char in value):
                return value
    return None
