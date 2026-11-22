"""Go /health/realtime access policy and operational snapshot response."""
import hmac
import ipaddress
from fastapi.responses import Response
from ..auth.profile_decode import go_trim_space
from ..infrastructure.go_response import marshal_map_json

_FORWARDING = ('x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto', 'x-real-ip', 'forwarded')


def _header_text(headers, name):
    # ASGI exposes header bytes through a Latin-1 string facade. Go's string
    # functions interpret their original bytes as UTF-8, preserving invalid
    # bytes for comparison instead of treating them as Unicode whitespace.
    return headers.get(name, '').encode('latin-1').decode('utf-8', errors='surrogateescape')


def direct_loopback(host, headers):
    if any(go_trim_space(_header_text(headers, name)) for name in _FORWARDING):
        return False
    if not host or '%' in host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return address.is_loopback


def has_bearer_token(headers, token):
    authorization = _header_text(headers, 'authorization')
    if len(authorization) <= 7 or authorization[:7].lower() != 'bearer ':
        return False
    candidate = go_trim_space(authorization[7:])
    return bool(candidate) and hmac.compare_digest(candidate.encode('utf-8', errors='surrogateescape'), token.encode('utf-8'))


def metrics_response(request, token, metrics, daemon_metrics):
    token = go_trim_space(token)
    if token:
        if not has_bearer_token(request.headers, token):
            return Response(b'unauthorized\n', status_code=401, media_type='text/plain',
                            headers={'WWW-Authenticate': 'Bearer realm="metrics"',
                                     'X-Content-Type-Options': 'nosniff'})
    elif not direct_loopback(request.client.host if request.client else '', request.headers):
        return Response(b'404 page not found\n', status_code=404, media_type='text/plain',
                        headers={'X-Content-Type-Options': 'nosniff'})
    snapshot = metrics.snapshot()
    snapshot['daemonws'] = daemon_metrics.snapshot()
    return Response(marshal_map_json(snapshot) + b'\n', media_type='application/json',
                    headers={'Cache-Control': 'no-store'})
