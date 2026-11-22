"""Go URL.Parse / Values.Set / URL.String behavior for signed URL queries."""
import re
from urllib.parse import quote_from_bytes, unquote_to_bytes
from workpal_backend.realtime.origins import url_host

_PATH_SAFE = '/:@&=+$,;-._~'
_FRAGMENT_SAFE = _PATH_SAFE + '?!()*'
_RAW_EXTRA = "!$&'()*+,;=:@[]%"
_HOST_SAFE = "-_.~!$&'()*+,;=:[]<>\""


def _bytes(value):
    return value.encode('utf8', 'surrogateescape')


def _escaped(raw, safe):
    allowed = safe + _RAW_EXTRA
    if all(ord(c) < 128 and (c.isalnum() or c in allowed) for c in raw):
        return raw
    return quote_from_bytes(unquote_to_bytes(_bytes(raw)), safe=safe)


def _query(raw, key, value):
    values = {}
    for component in _bytes(raw).split(b'&'):
        if not component or b';' in component or re.search(br'%(?![0-9a-fA-F]{2})', component):
            continue
        name, _, item = component.partition(b'=')
        name = unquote_to_bytes(name.replace(b'+', b' '))
        item = unquote_to_bytes(item.replace(b'+', b' '))
        values.setdefault(name, []).append(item)
    values[_bytes(key)] = [_bytes(value)]
    def escape(data):return quote_from_bytes(data, safe='').replace('%20', '+')
    return '&'.join(escape(name) + '=' + escape(item)
                    for name in sorted(values) for item in values[name])


def set_query_value(raw, key, value):
    """Return the untouched URL on parse failure, as the signing caller does."""
    try:
        host = url_host(raw)
    except ValueError:
        return raw
    source, _, fragment = raw.partition('#')
    path_source, _, query = source.partition('?')
    scheme_match = re.match(r'([A-Za-z][A-Za-z0-9+.-]*):', path_source)
    scheme = scheme_match.group(1).lower() if scheme_match else ''
    rest = path_source[scheme_match.end():] if scheme_match else path_source
    result = scheme + ':' if scheme else ''
    if scheme and not rest.startswith('/'):
        result += rest  # Opaque URLs retain their resource bytes.
    else:
        user = None
        if rest.startswith('//') and (scheme or not rest.startswith('///')):
            authority, separator, suffix = rest[2:].partition('/')
            rest = '/' + suffix if separator else ''
            if '@' in authority:
                user = authority.rsplit('@', 1)[0]
            if host or rest or user is not None:
                result += '//'
            if user is not None:
                username, colon, password = user.partition(':')
                safe = '$&+,;=-._~'
                result += quote_from_bytes(unquote_to_bytes(_bytes(username)), safe=safe)
                if colon:
                    result += ':' + quote_from_bytes(unquote_to_bytes(_bytes(password)), safe=safe)
                result += '@'
            result += quote_from_bytes(_bytes(host), safe=_HOST_SAFE)
        path = _escaped(rest, _PATH_SAFE)
        if not result and ':' in path.split('/', 1)[0]:
            result = './'
        result += path
    result += '?' + _query(query, key, value)
    if fragment:
        result += '#' + _escaped(fragment, _FRAGMENT_SAFE)
    return result
