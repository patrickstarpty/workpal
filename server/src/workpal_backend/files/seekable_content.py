"""Go ServeContent path for attachments: explicit type, zero modtime, no ETag.

Reader is asynchronous and seekable; caller owns its lifetime. Range and
precondition logic adapted from Go net/http (BSD license: GO_LICENSE.txt).
"""
import logging
import re
import secrets
from .ranges import _int64

_log = logging.getLogger(__name__)


def _star(value):
    # A wildcard after valid entity tags/commas matches even without an ETag.
    while value:
        value = value.strip(' \t\r\n')
        if value.startswith(','):
            value = value[1:]
            continue
        if value.startswith('*'):
            return True
        match = re.match(r'(?:W/)?"[\x21\x23-\x7e\x80-\U0010ffff]*"', value)
        if not match:
            return False
        value = value[match.end():]
    return False


def _ranges(value, size):
    if not value:
        return []
    if not value.startswith('bytes='):
        raise ValueError('invalid range')
    values = value[6:].split(',')
    if len(values) > 200:
        return []
    ranges = []
    no_overlap = False
    for item in values:
        item = item.strip(' \t\r\n')
        if not item:
            continue
        first, dash, last = item.partition('-')
        if not dash:
            raise ValueError('invalid range')
        first, last = first.strip(' \t\r\n'), last.strip(' \t\r\n')
        try:
            if not first:
                if not last or last.startswith('-'):
                    raise ValueError()
                count = _int64(last)
                if count < 0:
                    raise ValueError()
                count = min(count, size)
                start = size - count
            else:
                start = _int64(first)
                if start < 0:
                    raise ValueError()
                if start >= size:
                    no_overlap = True
                    continue
                end = size - 1 if not last else _int64(last)
                if end < start:
                    raise ValueError()
                count = min(end, size - 1) - start + 1
        except ValueError as error:
            raise ValueError('invalid range') from error
        ranges.append((start, count))
    if no_overlap and not ranges:
        raise ValueError('invalid range: failed to overlap')
    return ranges


async def serve_seekable_attachment(reader, send, *, headers, request_headers=None, method='GET'):
    response = dict(headers)
    request = request_headers or {}
    if b'etag' in response:
        raise ValueError('attachment ServeContent path does not set an ETag')

    async def begin(status):
        await send({'type':'http.response.start', 'status':status, 'headers':list(response.items())})

    async def finish():
        await send({'type':'http.response.body', 'body':b'', 'more_body':False})

    async def error(status, message):
        for key in (b'cache-control', b'content-encoding', b'etag', b'last-modified', b'content-length'):
            response.pop(key, None)
        response[b'content-type'] = b'text/plain; charset=utf-8'
        response[b'x-content-type-options'] = b'nosniff'
        await begin(status)
        await send({'type':'http.response.body', 'body':(message+'\n').encode(), 'more_body':False})

    if request.get('if-match') and not _star(request['if-match']):
        await begin(412)
        await finish()
        return
    if _star(request.get('if-none-match', '')):
        status = 304 if method in ('GET', 'HEAD') else 412
        if status == 304:
            for key in (b'content-type', b'content-length', b'content-encoding'):
                response.pop(key, None)
        await begin(status)
        await finish()
        return
    range_value = request.get('range', '')
    if method in ('GET', 'HEAD') and request.get('if-range'):
        range_value = ''
    try:
        size = await reader.seek(0, 2)
        await reader.seek(0, 0)
    except Exception:
        await error(500, "seeker can't seek")
        return
    if size < 0:
        await error(500, 'negative content size computed')
        return
    try:
        ranges = _ranges(range_value, size)
    except ValueError as failure:
        message = str(failure)
        if message == 'invalid range: failed to overlap' and size == 0:
            ranges = []
        else:
            if message == 'invalid range: failed to overlap':
                response[b'content-range'] = f'bytes */{size}'.encode()
            await error(416, message)
            return
    total = sum(count for _, count in ranges)
    # Go int64 accumulation wraps, although physical files rarely approach it.
    total = (total + (1 << 63)) % (1 << 64) - (1 << 63)
    if total > size:
        ranges = []
    status, length = 200, size
    prefixes = []
    suffix = b''
    if len(ranges) == 1:
        start, length = ranges[0]
        try:
            await reader.seek(start, 0)
        except Exception as failure:
            await error(416, str(failure))
            return
        status = 206
        response[b'content-range'] = f'bytes {start}-{start+length-1}/{size}'.encode()
    elif ranges:
        status = 206
        boundary = secrets.token_hex(30).encode()
        content_type = response.get(b'content-type', b'')
        for index, (start, count) in enumerate(ranges):
            prefixes.append((b'\r\n' if index else b'') + b'--' + boundary +
                f'\r\nContent-Range: bytes {start}-{start+count-1}/{size}\r\nContent-Type: '.encode() +
                content_type + b'\r\n\r\n')
        suffix = b'\r\n--' + boundary + b'--\r\n'
        length = sum(map(len, prefixes)) + len(suffix) + sum(count for _, count in ranges)
        response[b'content-type'] = b'multipart/byteranges; boundary=' + boundary
    response[b'accept-ranges'] = b'bytes'
    if ranges or not response.get(b'content-encoding'):
        response[b'content-length'] = str(length).encode()
    await begin(status)
    if method == 'HEAD':
        await finish()
        return

    async def copy(count):
        while count:
            data = await reader.read(min(count, 32768))
            if not data:
                raise EOFError('short attachment content')
            await send({'type':'http.response.body', 'body':data, 'more_body':True})
            count -= len(data)

    try:
        if prefixes:
            for prefix, (start, count) in zip(prefixes, ranges):
                await send({'type':'http.response.body', 'body':prefix, 'more_body':True})
                await reader.seek(start, 0)
                await copy(count)
            await send({'type':'http.response.body', 'body':suffix, 'more_body':True})
        else:
            await copy(length)
    except Exception:
        _log.exception('Failed to stream seekable attachment')
    await finish()
