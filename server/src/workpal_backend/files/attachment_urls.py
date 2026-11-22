"""Canonical attachment URL persistence and download-mode policy."""
import re
from workpal_backend.auth.profile_decode import go_trim_space
from workpal_backend.workspaces.decode import go_lower
from workpal_backend.realtime.origins import url_host
from workpal_backend.realtime.request_values import query_value


def durable_public_url(raw):
    scheme = re.match(r'([A-Za-z][A-Za-z0-9+.-]*):', raw)
    if not scheme or scheme.group(1).lower() not in ('http', 'https'):
        return False
    try:
        if not url_host(raw):
            return False
    except ValueError:
        return False
    query = raw.partition('#')[0].partition('?')[2].encode('utf8', 'surrogateescape')
    return not any(query_value(query, key) for key in (
        'Signature', 'X-Amz-Signature', 'Key-Pair-Id', 'Expires', 'X-Amz-Expires'))


def normalize_download_mode(raw):
    value = go_lower(go_trim_space(raw))
    if value in ('', 'auto'):
        return 'auto', True
    if value in ('cloudfront', 'presign', 'proxy'):
        return value, True
    return 'auto', False


def download_ttl(configured_nanoseconds):
    return configured_nanoseconds if configured_nanoseconds > 0 else 1800 * 10**9


def stable_urls_requested(first_capabilities_header):
    return any(go_trim_space(value) == 'stable_attachment_urls'
               for value in first_capabilities_header.split(','))


class AttachmentURLs:
    def __init__(self, storage=None, signer=None, *, public_url=''):
        self.storage = storage
        self.signer = signer
        self.public_url = public_url.rstrip('/')

    def publicly_readable(self, raw):
        if self.storage is None or self.storage.is_local or self.signer is not None:
            return False
        return bool(self.storage.cdn_domain()) and durable_public_url(raw)

    def markdown_url(self, attachment_id, storage_url):
        if self.publicly_readable(storage_url):
            return storage_url
        return self.public_url + '/api/attachments/' + attachment_id + '/download'


def should_proxy_url(raw):
    import ipaddress
    try:
        host = url_host(raw)
    except ValueError:
        return True
    if host.startswith('['):
        host = host[1:host.rfind(']')]
    elif ':' in host:
        host = host.rsplit(':', 1)[0]
    host = go_lower(go_trim_space(host).removesuffix('.'))
    if (not host or host == 'localhost' or '.' not in host or
            host.endswith(('.localhost', '.local', '.localdomain', '.internal', '.lan', '.home', '.docker'))):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    original = address
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    if isinstance(address, ipaddress.IPv4Address):
        return (int(address) == 0 and isinstance(original, ipaddress.IPv4Address)) or any(address in ipaddress.ip_network(network) for network in (
            '127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
            '169.254.0.0/16', '224.0.0.0/24'))
    return (int(address) == 0 and address.scope_id is None) or any(address in ipaddress.ip_network(network) for network in (
        '::1/128', 'fc00::/7', 'fe80::/10', 'ff02::/16'))


def resolve_download_mode(configured, raw_url, *, signer=False, presigner=False):
    mode, _ = normalize_download_mode(configured)
    if mode != 'auto':
        return mode
    if signer:
        return 'cloudfront'
    if should_proxy_url(raw_url):
        return 'proxy'
    return 'presign' if presigner else 'proxy'
