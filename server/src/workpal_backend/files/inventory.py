"""Attachment listing for an already-authorized issue."""
from asyncio import CancelledError
from functools import partial
from starlette.responses import Response

from ..infrastructure.go_time import format_timestamp
from ..infrastructure.go_response import GoJSONResponse
from ..issues.loader import IssueLoadError
from .attachment_io import _joined_call
from .content import _error
from .loader import AttachmentLoadError
from .metadata import ordered_attachment_response


class AttachmentInventory:
    def __init__(self, queries, metadata):
        self.queries = queries
        self.metadata = metadata

    def list(self, issue, *, stable=False):
        try:
            attachments = self.queries.list_attachments_by_issue(issue['id'], issue['workspace_id'])
            identities = list(dict.fromkeys(row['comment_id'] for row in attachments if row.get('comment_id') is not None))
            origins = {}
            if identities:
                origins = {row['id']: row for row in self.queries.list_comment_origins_for_issue(
                    identities, issue['id'], issue['workspace_id'])}
        except (Exception, CancelledError) as error:
            raise AttachmentLoadError(500, 'failed to list attachments') from error
        result = []
        for attachment in attachments:
            response = self.metadata.response(attachment, stable=stable)
            origin = origins.get(attachment.get('comment_id'))
            if origin is not None:
                response.update(comment_author_type=origin['author_type'],
                                comment_author_id=origin.get('author_id') or '',
                                comment_created_at=format_timestamp(origin.get('created_at')))
            result.append(ordered_attachment_response(response))
        return result


class AttachmentListing:
    def __init__(self, issue_loader, inventory):
        self.issue_loader, self.inventory = issue_loader, inventory

    async def list(self, issue_id, user_id, workspace_id, *, stable=False):
        try:
            issue = await _joined_call(self.issue_loader.for_user, issue_id, user_id, workspace_id)
            rows = await _joined_call(partial(self.inventory.list, stable=stable), issue)
        except (IssueLoadError, AttachmentLoadError) as error:
            return Response(status_code=499) if error.status == 499 else _error(error.status, error.message)
        return GoJSONResponse(rows)
