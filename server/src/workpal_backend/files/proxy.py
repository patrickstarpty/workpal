"""Authorized attachment download proxy with owned reader cleanup."""
from asyncio import CancelledError
from ..infrastructure.request_cancellation import is_request_cancellation
from .attachment_io import open_attachment_reader
from .content import _error
from .content_disposition import content_disposition
from .preview_security import preview_csp
from .range_stream import serve_proxy_range
from .seekable_content import serve_seekable_attachment


async def proxy_attachment(attachment, storage, key, send, *, method='GET',
                           request_headers=None, frame_ancestors=(),
                           force_attachment=False, request_error=lambda: None,
                           response_headers=()):
    initial_headers = dict(response_headers)
    async def cancelled():
        await send({'type':'http.response.start', 'status':499, 'headers':list(initial_headers.items())})
        await send({'type':'http.response.body', 'body':b'', 'more_body':False})

    try:
        reader = await open_attachment_reader(storage, key)
    except (Exception, CancelledError) as error:
        if is_request_cancellation(request_error(), error):
            await cancelled()
        else:
            response = _error(404, 'attachment object not found')
            response.raw_headers = list({**initial_headers, **dict(response.raw_headers)}.items())
            await response({'type':'http'}, None, send)
        return
    try:
        parent_error = request_error()
        if is_request_cancellation(parent_error, parent_error):
            await cancelled()
            return
        media_type = attachment['content_type']
        headers = {**initial_headers,
            b'content-type':(media_type or 'application/octet-stream').encode(),
            b'content-disposition':content_disposition(media_type, attachment['filename'],
                force_attachment=force_attachment).encode(),
            b'cache-control':b'no-store',
            b'x-content-type-options':b'nosniff',
            b'content-security-policy':preview_csp(frame_ancestors).encode(),
        }
        if reader.seekable:
            await serve_seekable_attachment(reader, send, headers=headers,
                request_headers=request_headers, method=method)
        else:
            await serve_proxy_range(reader, attachment['size_bytes'],
                (request_headers or {}).get('range', ''), send, headers=headers)
    finally:
        await reader.close()
