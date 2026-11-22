"""WebSocket origin checks and router origin/proxy configuration."""
import ipaddress
import re
from urllib.parse import unquote_to_bytes
from ..auth.profile_decode import go_trim_space

_DEFAULTS = ['http://localhost:3000', 'http://localhost:5173', 'http://localhost:5174']
_HOST_PUNCTUATION = "-_.~!$&'()*+,;=:[]<>\""


def router_origins(env):
    raw = go_trim_space(env.get('CORS_ALLOWED_ORIGINS', '')) or go_trim_space(env.get('FRONTEND_ORIGIN', ''))
    origins = [value for part in raw.split(',') if (value := go_trim_space(part))]
    return origins or list(_DEFAULTS)


def _valid_escapes(value):
    if re.search(r'%(?![0-9a-fA-F]{2})', value):
        raise ValueError('invalid URL escape')


def _host_unescape(value, zone=False):
    _valid_escapes(value)
    position = 0
    while position < len(value):
        char = value[position]
        if char == '%':
            byte = int(value[position+1:position+3], 16)
            if not zone and byte < 128 and byte != 37:
                raise ValueError('escaped ASCII host')
            if zone and byte not in (32, 37) and not (chr(byte).isascii() and (chr(byte).isalnum() or chr(byte) in _HOST_PUNCTUATION)):
                raise ValueError('invalid zone escape')
            position += 3
        else:
            if ord(char) < 128 and not (char.isalnum() or char in _HOST_PUNCTUATION):
                raise ValueError('invalid host character')
            position += 1
    return unquote_to_bytes(value).decode('utf-8', errors='surrogateescape')


def _optional_port(value):
    return not value or re.fullmatch(r':[0-9]*', value) is not None


def url_host(raw):
    """Host selection under pinned Go net/url semantics used by checkOrigin."""
    source, _, fragment = raw.partition('#')
    _valid_escapes(fragment)
    if any(ord(char) < 32 or ord(char) == 127 for char in source):
        raise ValueError('URL control character')
    match = re.match(r'([A-Za-z][A-Za-z0-9+.-]*):', source)
    scheme = match.group(1).lower() if match else ''
    rest = source[match.end():] if match else source
    rest = rest.split('?', 1)[0]
    if not rest.startswith('/'):
        if scheme:
            return ''
        if ':' in rest.split('/', 1)[0]:
            raise ValueError('relative URL colon')
    host = ''
    if (scheme or not rest.startswith('///')) and rest.startswith('//'):
        authority, _, path = rest[2:].partition('/')
        rest = path
        if '@' in authority:
            user, authority = authority.rsplit('@', 1)
            if any(not (char.isascii() and (char.isalnum() or char in "-._:~!$&'()*+,;=%@")) for char in user):
                raise ValueError('invalid userinfo')
            _valid_escapes(user)
        opening = authority.rfind('[')
        if opening > 0:
            raise ValueError('invalid IP literal')
        if opening == 0:
            closing = authority.rfind(']')
            if closing < 0 or not _optional_port(authority[closing+1:]):
                raise ValueError('invalid bracketed host')
            address = authority[1:closing]
            zone = address.find('%25')
            address = (_host_unescape(address[:zone]) + _host_unescape(address[zone:], True)
                       if zone >= 0 else _host_unescape(address))
            if ipaddress.ip_address(address).version != 6:
                raise ValueError('invalid IP literal')
            host = '[' + address + ']' + authority[closing+1:]
        else:
            colon = authority.find(':') if scheme in ('http', 'https') else authority.rfind(':')
            if colon >= 0 and not _optional_port(authority[colon:]):
                raise ValueError('invalid port')
            host = _host_unescape(authority)
    _valid_escapes(rest)
    return host


def _equal_fold(left, right):
    # EqualFold uses simple Unicode folds; multi-character expansions do not
    # equate a single rune (e.g. sharp-s) with multiple characters.
    def fold(char):
        folded = char.casefold()
        return folded if len(folded) == 1 else char.lower()
    return len(left) == len(right) and all(fold(a) == fold(b) for a, b in zip(left, right))


class OriginPolicy:
    def __init__(self, origins, trusted_proxies=()):
        self.origins = tuple(origins)
        self.proxies = []
        for value in trusted_proxies:
            try:
                if '/' not in value or '%' in value or re.fullmatch(r'0|[1-9][0-9]*', value.rsplit('/', 1)[-1]) is None:
                    continue
                self.proxies.append(ipaddress.ip_network(value, strict=False))
            except ValueError:
                pass

    def trusted(self, remote):
        host = remote
        if remote.startswith('[') and ']:' in remote:
            candidate, port = remote[1:].split(']:', 1)
            if ':' not in port:
                host = candidate
        elif remote.count(':') == 1:
            host = remote.split(':', 1)[0]
        host = host.strip('[]')
        if '%' in host:
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return False
        address = getattr(address, 'ipv4_mapped', None) or address
        return any(address in prefix for prefix in self.proxies)

    def allowed(self, origin, host, remote, forwarded_host=''):
        if not origin:
            return True
        try:
            parsed = url_host(origin)
        except ValueError:
            parsed = None
        if parsed is not None and _equal_fold(parsed, host):
            return True
        forwarded = go_trim_space(forwarded_host.split(',', 1)[0])
        if forwarded and self.trusted(remote) and parsed is not None and _equal_fold(parsed, forwarded):
            return True
        return origin in self.origins
