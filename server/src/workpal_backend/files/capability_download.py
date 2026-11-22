"""Redeem a single-attachment capability without repeating session auth."""
import asyncio
import time
from ..infrastructure.go_uuid import parse_uuid
from ..realtime.request_values import query_value
from .attachment_io import _joined_call
from .content import _error
from .preview_security import preview_csp
from .proxy import proxy_attachment


async def redeem_attachment(attachment_id, raw_query, queries, storage, capabilities,
                            send, *, method='GET', request_headers=None,
                            frame_ancestors=(), request_error=lambda: None,
                            clock_ns=time.time_ns):
    async def error(status, message, code=None):
        await _error(status, message, code)({'type':'http'}, None, send)

    intent = 'attachment' if query_value(raw_query, 'dl') == '1' else ''
    if not capabilities.verify(attachment_id, query_value(raw_query, 'exp'),
            query_value(raw_query, 'sig'), intent=intent, now_ns=clock_ns()):
        await error(403, 'invalid or expired download link')
        return
    try:
        identity = parse_uuid(attachment_id)
    except ValueError:
        await error(400, 'invalid attachment id')
        return
    try:
        attachment = await _joined_call(queries.get_attachment_by_id, identity)
    except (Exception, asyncio.CancelledError):
        await error(404, 'attachment not found')
        return
    if storage is None:
        await error(403, 'storage not configured', 'storage_not_configured')
        return
    await proxy_attachment(attachment, storage, storage.key_from_url(attachment['url']),
        send, method=method, request_headers=request_headers,
        frame_ancestors=frame_ancestors, request_error=request_error,
        force_attachment=intent == 'attachment', response_headers={
            b'content-security-policy':preview_csp(frame_ancestors).encode(),
            b'referrer-policy':b'no-referrer',
        })
