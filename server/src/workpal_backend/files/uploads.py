"""Upload orchestration after trusted identity/wakeup attribution capture.

Writer.create owns the wakeup transaction; create_for_live_comment additionally
locks and rechecks a live comment. on_created owns revision-event publication.
These adapters are required: no local mock writes or fabricated events occur.
"""
from asyncio import CancelledError
import logging
from starlette.responses import Response
from ..infrastructure.go_response import GoJSONResponse
from ..infrastructure.query_errors import NoRows
from ..infrastructure.request_cancellation import is_request_cancellation
from ..infrastructure.uuid7 import uuid7
from .attachment_io import _joined_call
from .avatar_urls import extension
from .content import _error
from .form_values import form_value
from .image_dimensions import dimensions
from .loader import AttachmentLoadError
from .mime_sniff import upload_content_type
from .upload_form import parse_upload_form, UploadFormError

_log = logging.getLogger(__name__)


class AttachmentUploads:
    def __init__(self, storage, bindings, writer, metadata, *, on_created, new_id=uuid7):
        self.storage, self.bindings, self.writer = storage, bindings, writer
        self.metadata, self.on_created, self.new_id = metadata, on_created, new_id

    async def upload(self, body, content_type, user_id, workspace_id, *, raw_query=b'',
                     stable=False, actor_source='', agent_id='', task_id='',
                     request_error=lambda: None):
        if self.storage is None:
            return _error(403, 'file upload not configured', 'file_upload_not_configured')
        if not user_id:
            return _error(401, 'user not authenticated')
        try:
            form = await parse_upload_form(body, content_type, raw_query=raw_query)
        except UploadFormError as error:
            return _error(error.status, error.detail)
        try:
            try:
                file = form.first_file()
            except UploadFormError as error:
                return _error(error.status, error.detail)
            try:
                prefix = await file.read(512)
            except (Exception, CancelledError):
                return _error(400, 'failed to read file')
            media_type = upload_content_type(prefix, file.filename)
            try:
                await file.seek(0)
            except (Exception, CancelledError):
                return _error(500, 'failed to read file')
            try:
                data = await file.read()
            except (Exception, CancelledError):
                return _error(400, 'failed to read file')
            try:
                identity = self.new_id()
            except Exception:
                return _error(500, 'internal error')
            filename = identity + extension(file.filename)
            key = ('workspaces/' + workspace_id if workspace_id else 'users/' + user_id) + '/' + filename
            params = None
            if workspace_id:
                values = {field:form_value(form, field, raw_query) for field in
                          ('issue_id','comment_id','chat_session_id','task_id')}
                try:
                    params = await _joined_call(lambda:self.bindings.resolve(user_id, workspace_id,
                        values, actor_source=actor_source, agent_id=agent_id, task_id=task_id))
                except AttachmentLoadError as error:
                    return Response(status_code=499) if error.status == 499 else _error(error.status, error.message)
                params.update(id=identity, filename=file.filename, content_type=media_type, size_bytes=len(data))
                size = dimensions(data)
                if size is not None:
                    params.update(width=size[0], height=size[1])
            try:
                link = await _joined_call(self.storage.upload, key, data, media_type, file.filename)
            except (Exception, CancelledError) as error:
                if is_request_cancellation(request_error(), error):
                    return Response(status_code=499)
                _log.warning('File upload failed: %s', error)
                return _error(500, 'upload failed')
            if params is None:
                return GoJSONResponse(dict(filename=file.filename, id=identity, url=link))
            params['url'] = link
            comment = params.get('comment_id') is not None
            try:
                create = self.writer.create_for_live_comment if comment else self.writer.create
                row = await _joined_call(create, params)
            except (Exception, CancelledError) as error:
                if comment and isinstance(error, NoRows):
                    try:
                        await _joined_call(self.storage.delete_keys, [self.storage.key_from_url(link)])
                    except (Exception, CancelledError):
                        _log.warning('Failed to remove refused comment upload')
                    return _error(403, 'invalid comment_id')
                if is_request_cancellation(request_error(), error):
                    # The transaction may have committed: keep the object.
                    return Response(status_code=499)
                _log.warning('Failed to create attachment record: %s', error)
                return GoJSONResponse(dict(filename=file.filename, id='', url=link))
            await _joined_call(self.on_created, row, params.uploader)
            return GoJSONResponse(self.metadata.response(row, stable=stable))
        finally:
            try:
                await form.close()
            except Exception:
                _log.warning('Failed to remove multipart temporary files')
