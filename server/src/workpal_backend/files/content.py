"""Bounded text-preview service for an already-authorized attachment.

Run this synchronous storage operation in the HTTP worker thread. Loading the
attachment and enforcing workspace/project access belong to the caller.
"""
import json
import logging
from asyncio import CancelledError
from starlette.responses import Response
from .preview import is_text_previewable
from .preview_security import preview_csp

log = logging.getLogger(__name__)
DEFAULT_MAX_SIZE = 2 << 20
MAX_SIZE = 16 << 20


def effective_max_size(size):
    return DEFAULT_MAX_SIZE if size <= 0 else min(size, MAX_SIZE)


def _error(status, message, code=None):
    value = {'error': message}
    if code is not None:
        value['code'] = code
    body = json.dumps(value, sort_keys=True, separators=(',', ':')).encode() + b'\n'
    return Response(body, status_code=status, media_type='application/json')


def render_text_preview(attachment, storage, *, max_size=DEFAULT_MAX_SIZE, frame_ancestors=()):
    if not is_text_previewable(attachment['content_type'], attachment['filename']):
        return _error(415, 'preview not supported for this file type')
    if storage is None:
        return _error(403, 'storage not configured', 'storage_not_configured')
    limit = effective_max_size(max_size)
    if attachment['size_bytes'] > limit:
        return _error(413, 'file too large for inline preview')
    key = storage.key_from_url(attachment['url'])
    try:
        reader = storage.get_reader(key)
    except (Exception, CancelledError):
        log.exception('Failed to open attachment preview')
        return _error(404, 'attachment object not found')
    body = bytearray()
    try:
        try:
            while len(body) < limit + 1:
                data = reader.read(limit + 1 - len(body))
                if not data:
                    break
                body.extend(data)
        except (Exception, CancelledError):
            log.exception('Failed to read attachment preview')
            return _error(502, 'failed to read attachment body')
    finally:
        try:
            reader.close()
        except (Exception, CancelledError):
            pass  # Go's deferred reader.Close discards this error.
    if len(body) > limit:
        return _error(413, 'file too large for inline preview')
    return Response(bytes(body), headers={
        'Content-Type': 'text/plain; charset=utf-8',
        'X-Original-Content-Type': attachment['content_type'],
        'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': preview_csp(frame_ancestors),
    })
