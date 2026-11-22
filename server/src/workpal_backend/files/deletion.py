"""Authorized attachment deletion with post-commit events and object cleanup."""
from asyncio import CancelledError
from starlette.responses import Response

from ..infrastructure.query_errors import NoRows
from .attachment_io import _joined_call
from .content import _error
from .loader import AttachmentLoadError


class AttachmentDeletion:
    def __init__(self, loader, writer, events, storage):
        self.loader, self.writer, self.events, self.storage = loader, writer, events, storage

    async def delete(self, attachment_id, user_id, workspace_id, *, member=None):
        if not workspace_id:
            return _error(400, 'workspace_id is required')
        if not user_id:
            return _error(401, 'user not authenticated')
        try:
            attachment = await _joined_call(self.loader.for_request, attachment_id, workspace_id)
        except AttachmentLoadError as error:
            return Response(status_code=499) if error.status == 499 else _error(error.status, error.message)
        if attachment.get('source_context_id') is not None:
            return _error(404, 'attachment not found')
        uploader = attachment.get('uploader_type') == 'member' and (attachment.get('uploader_id') or '') == user_id
        admin = member is not None and member.get('role') in ('admin', 'owner')
        if not uploader and not admin:
            return _error(403, 'not authorized to delete this attachment')
        def write(queries):
            return queries.delete_attachment(attachment['id'], attachment['workspace_id'])
        try:
            deleted = await _joined_call(self.writer.with_owner_lock, attachment, write)
        except NoRows:
            return _error(404, 'attachment not found')
        except (Exception, CancelledError):
            return _error(500, 'failed to delete attachment')
        await _joined_call(self.events.deleted, attachment, deleted)
        if self.storage is not None and attachment.get('url'):
            try:
                key = self.storage.key_from_url(attachment['url'])
                await _joined_call(self.storage.delete, key)
            except (Exception, CancelledError):
                # The storage interface's deletion is best effort after commit.
                pass
        return Response(status_code=204)
