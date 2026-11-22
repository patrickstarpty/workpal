"""Canonical attachment response projection and durable URL selection."""
import asyncio
import logging
import time
from .attachment_urls import AttachmentURLs, download_ttl, resolve_download_mode
from .attachment_io import _joined_call
from .content_disposition import content_disposition
from ..infrastructure.go_uuid import parse_uuid
from ..infrastructure.go_time import format_timestamp

_log = logging.getLogger(__name__)

_RESPONSE_FIELDS = ('id', 'workspace_id', 'issue_id', 'comment_id', 'chat_session_id',
    'chat_message_id', 'uploader_type', 'uploader_id', 'filename', 'url', 'download_url',
    'attachment_download_url', 'markdown_url', 'comment_author_type', 'comment_author_id',
    'comment_created_at', 'content_type', 'size_bytes', 'created_at', 'width', 'height')


def ordered_attachment_response(response):
    """Preserve the Go response struct's field order after optional enrichment."""
    return {**{key: response[key] for key in _RESPONSE_FIELDS if key in response},
            **{key: value for key, value in response.items() if key not in _RESPONSE_FIELDS}}


def _timestamp(value):
    return format_timestamp(value, invalid='0001-01-01T00:00:00Z')

class AttachmentMetadata:
    def __init__(self, storage=None, signer=None, *, public_url='', ttl_nanoseconds=0,
                 clock_ns=time.time_ns, mode='auto', capabilities=None):
        self.storage = storage
        self.signer = signer
        self.urls = AttachmentURLs(storage, signer, public_url=public_url)
        self.ttl = download_ttl(ttl_nanoseconds)
        self.clock_ns = clock_ns
        self.mode = mode
        self.capabilities = capabilities

    def response(self, attachment, *, stable=False):
        def identity(key):
            value = attachment.get(key)
            return parse_uuid(value) if value is not None else None
        attachment_id = identity('id') or ''
        response = {
            'id':attachment_id,
            'workspace_id':identity('workspace_id') or '',
            **{key:identity(key) for key in ('issue_id','comment_id','chat_session_id','chat_message_id')},
            'uploader_type':attachment['uploader_type'],
            'uploader_id':identity('uploader_id') or '',
            'filename':attachment['filename'],
            'url':attachment['url'],
            'download_url':f'/api/attachments/{attachment_id}/download',
            'markdown_url':self.urls.markdown_url(attachment_id, attachment['url']),
            'content_type':attachment['content_type'],
            'size_bytes':attachment['size_bytes'],
            'created_at':_timestamp(attachment.get('created_at')),
        }
        bound = any(attachment.get(key) is not None for key in
            ('issue_id','comment_id','chat_session_id','chat_message_id','task_id'))
        if self.storage is not None and self.storage.is_local and bound:
            response['url'] = response['markdown_url']
        if self.signer is not None and not stable:
            response['download_url'] = self.signer.signed_url(attachment['url'],
                (self.clock_ns() + self.ttl) // 10**9)
        if attachment.get('width') is not None and attachment.get('height') is not None:
            response['width'] = attachment['width']
            response['height'] = attachment['height']
        return ordered_attachment_response(response)

    async def signed_response(self, attachment):
        response = self.response(attachment)
        presign = getattr(self.storage, 'presign_get_with_content_disposition', None)
        mode = resolve_download_mode(self.mode, attachment['url'],
            signer=self.signer is not None, presigner=callable(presign))
        disposition = content_disposition(attachment['content_type'],
            attachment['filename'], force_attachment=True)
        if mode == 'cloudfront':
            if self.signer is not None:
                url = self.signer.signed_url_with_content_disposition(attachment['url'],
                    disposition, (self.clock_ns() + self.ttl) // 10**9)
                if url:
                    response['attachment_download_url'] = url
        elif mode == 'presign' and callable(presign):
            key = self.storage.key_from_url(attachment['url'])
            for field, value in (('download_url',''), ('attachment_download_url',disposition)):
                try:
                    url = await _joined_call(presign, key, self.ttl, value)
                except (Exception, asyncio.CancelledError) as error:
                    _log.warning('Failed to presign attachment URL: %s', error)
                else:
                    if url or field == 'download_url':
                        response[field] = url
        elif mode == 'proxy':
            if self.capabilities is None:
                raise RuntimeError('attachment capability signer not configured')
            response['download_url'] = self.capabilities.path(response['id'], now_ns=self.clock_ns())
            response['attachment_download_url'] = self.capabilities.path(response['id'],
                now_ns=self.clock_ns(), download=True)
        return ordered_attachment_response(response)
