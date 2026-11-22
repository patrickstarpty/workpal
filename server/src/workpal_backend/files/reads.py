"""Authorized attachment metadata and bounded text reads."""
from functools import partial
from starlette.responses import Response

from ..infrastructure.go_response import GoJSONResponse
from .attachment_io import _joined_call
from .content import DEFAULT_MAX_SIZE, _error, render_text_preview
from .loader import AttachmentLoadError


def _load_error(error):
    return Response(status_code=499) if error.status == 499 else _error(error.status, error.message)


class AttachmentReads:
    def __init__(self, loader, metadata, storage, *, max_preview_size=DEFAULT_MAX_SIZE,
                 frame_ancestors=()):
        self.loader, self.projection, self.storage = loader, metadata, storage
        self.max_preview_size, self.frame_ancestors = max_preview_size, frame_ancestors

    async def metadata(self, attachment_id, workspace_id, user_id, *, for_download=False):
        try:
            if for_download:
                attachment = await _joined_call(self.loader.for_download, attachment_id, user_id)
            else:
                attachment = await _joined_call(self.loader.for_request, attachment_id, workspace_id)
        except AttachmentLoadError as error:
            return _load_error(error)
        return GoJSONResponse(await self.projection.signed_response(attachment))

    async def content(self, attachment_id, workspace_id):
        try:
            attachment = await _joined_call(self.loader.for_request, attachment_id, workspace_id)
        except AttachmentLoadError as error:
            return _load_error(error)
        return await _joined_call(partial(render_text_preview, max_size=self.max_preview_size,
                                         frame_ancestors=self.frame_ancestors), attachment, self.storage)
