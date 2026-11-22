"""Canonical download orchestration with caller-resolved authentication.

The loader owns permission checks. Storage clients and database sessions are
caller-owned; this service makes no model calls or production connections.
"""
import asyncio
import time
from starlette.responses import Response
from .attachment_io import _joined_call
from .attachment_urls import download_ttl, resolve_download_mode
from .content import _error
from .content_disposition import content_disposition
from .loader import AttachmentLoadError
from .preview_security import preview_csp
from .proxy import proxy_attachment
from .redirect import download_redirect


class AttachmentDownloads:
    def __init__(self, loader, storage, *, signer=None, mode='auto',
                 ttl_nanoseconds=0, frame_ancestors=(), clock_ns=time.time_ns):
        self.loader = loader
        self.storage = storage
        self.signer = signer
        self.mode = mode
        self.ttl = download_ttl(ttl_nanoseconds)
        self.frame_ancestors = frame_ancestors
        self.clock_ns = clock_ns

    async def download(self, attachment_id, user_id, send, *, method='GET',
                       request_path='/', request_headers=None,
                       request_error=lambda: None):
        async def respond(response):
            await response({'type':'http'}, None, send)

        try:
            attachment = await _joined_call(self.loader.for_download, attachment_id, user_id)
        except AttachmentLoadError as error:
            await respond(Response(status_code=499) if error.status == 499 else
                          _error(error.status, error.message))
            return
        if self.storage is None:
            await respond(_error(403, 'storage not configured', 'storage_not_configured'))
            return
        key = self.storage.key_from_url(attachment['url'])
        presign = getattr(self.storage, 'presign_get_with_content_disposition', None)
        mode = resolve_download_mode(self.mode, attachment['url'],
            signer=self.signer is not None, presigner=callable(presign))
        disposition = content_disposition(attachment['content_type'],
            attachment['filename'], force_attachment=True)
        if mode == 'cloudfront':
            if self.signer is None:
                await respond(_error(500, 'cloudfront attachment downloads are not configured'))
                return
            url = self.signer.signed_url_with_content_disposition(attachment['url'],
                disposition, (self.clock_ns() + self.ttl) // 10**9)
        elif mode == 'presign':
            if not callable(presign):
                await respond(_error(500, 'attachment storage does not support presigned downloads'))
                return
            try:
                url = await _joined_call(presign, key, self.ttl, disposition)
            except (Exception, asyncio.CancelledError):
                await respond(_error(502, 'failed to create download URL'))
                return
        elif mode == 'proxy':
            await proxy_attachment(attachment, self.storage, key, send,
                method=method, request_headers=request_headers,
                frame_ancestors=self.frame_ancestors, request_error=request_error)
            return
        else:
            await respond(_error(500, 'invalid attachment download mode'))
            return
        await respond(download_redirect(url, method=method, request_path=request_path,
            headers={'Content-Security-Policy':preview_csp(self.frame_ancestors)}))
