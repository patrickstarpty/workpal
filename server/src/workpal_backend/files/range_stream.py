"""ASGI streaming for Go's forward-only attachment download path.

The caller owns the reader lifetime and attachment authorization. Seekable
storage uses a separate ServeContent path; do not use this for multipart ranges.
"""
import logging
from workpal_backend.auth.profile_decode import go_trim_space
from .ranges import parse_single_byte_range, RangeOutcome

log = logging.getLogger(__name__)


async def serve_proxy_range(reader, total, range_header, send, *, headers=()):
    response_headers = dict(headers)
    response_headers[b'accept-ranges'] = b'bytes'

    async def begin(status):
        await send({'type': 'http.response.start', 'status': status,
                    'headers': list(response_headers.items())})

    async def error(status, message):
        body = ('{"error":"' + message + '"}\n').encode()
        response_headers[b'content-type'] = b'application/json'
        response_headers[b'content-length'] = str(len(body)).encode()
        await begin(status)
        await send({'type': 'http.response.body', 'body': body, 'more_body': False})

    value = go_trim_space(range_header)
    full = not value or total < 0
    start = length = 0
    if not full:
        start, length, outcome = parse_single_byte_range(value, total)
        if outcome == RangeOutcome.UNSUPPORTED:
            full = True
        elif outcome == RangeOutcome.UNSATISFIABLE:
            response_headers[b'content-range'] = f'bytes */{total}'.encode()
            await error(416, 'requested range not satisfiable')
            return
    if not full and start:
        remaining = start
        try:
            while remaining:
                data = await reader.read(min(32768, remaining))
                if not data:
                    raise EOFError('short attachment while skipping range')
                remaining -= len(data)
        except Exception:
            log.exception('Failed to skip to attachment range start')
            await error(502, 'failed to read attachment range')
            return
    if full:
        if total >= 0:
            response_headers[b'content-length'] = str(total).encode()
        await begin(200)
        remaining = None
    else:
        response_headers[b'content-range'] = f'bytes {start}-{start+length-1}/{total}'.encode()
        response_headers[b'content-length'] = str(length).encode()
        await begin(206)
        remaining = length
    try:
        while remaining is None or remaining > 0:
            data = await reader.read(32768 if remaining is None else min(32768, remaining))
            if not data:
                if remaining:
                    raise EOFError('short attachment range')
                break
            try:
                await send({'type': 'http.response.body', 'body': data, 'more_body': True})
            except Exception:
                log.exception('Failed to write attachment stream')
                return
            if remaining is not None:
                remaining -= len(data)
    except Exception:
        # Headers have already been committed; retain that status, as Go does.
        log.exception('Failed to stream attachment')
    await send({'type': 'http.response.body', 'body': b'', 'more_body': False})
