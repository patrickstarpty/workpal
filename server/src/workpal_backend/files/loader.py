"""Attachment loading after the HTTP layer resolves trusted request identity.

The caller supplies request-specific project visibility and owns the database
session. Downloads derive workspace from the attachment, never a query string.
"""
from asyncio import CancelledError
from ..auth.membership_cache import MembershipCache
from ..infrastructure.go_uuid import parse_uuid
from ..infrastructure.request_cancellation import is_query_cancellation
from .access import attachment_in_hidden_project


class AttachmentLoadError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _identity(value, field):
    try:
        return parse_uuid(value)
    except ValueError as error:
        raise AttachmentLoadError(400, 'invalid ' + field) from error


class AttachmentLoader:
    def __init__(self, queries, *, hidden_projects, membership_cache=None,
                 request_error=lambda: None):
        self.queries = queries
        self.hidden_projects = hidden_projects
        self.cache = membership_cache if membership_cache is not None else MembershipCache()
        self.request_error = request_error

    def _visible(self, workspace, attachment):
        if attachment.get('issue_id') is None and attachment.get('comment_id') is None:
            return attachment
        try:
            hidden = self.hidden_projects(workspace)
        except (Exception, CancelledError) as error:
            if is_query_cancellation(self.request_error(), error):
                raise AttachmentLoadError(499, '') from error
            raise AttachmentLoadError(500, 'failed to resolve project access') from error
        try:
            denied = attachment_in_hidden_project(self.queries, hidden, attachment)
        except (Exception, CancelledError) as error:
            raise AttachmentLoadError(500, 'failed to resolve project access') from error
        if denied:
            raise AttachmentLoadError(404, 'attachment not found')
        return attachment

    def for_request(self, attachment_id, workspace_id):
        if not workspace_id:
            raise AttachmentLoadError(400, 'workspace_id is required')
        identity = _identity(attachment_id, 'attachment id')
        workspace = _identity(workspace_id, 'workspace id')
        try:
            attachment = self.queries.get_attachment(identity, workspace)
        except (Exception, CancelledError) as error:
            raise AttachmentLoadError(404, 'attachment not found') from error
        return self._visible(workspace_id, attachment)

    def for_download(self, attachment_id, user_id):
        identity = _identity(attachment_id, 'attachment id')
        try:
            attachment = self.queries.get_attachment_by_id(identity)
        except (Exception, CancelledError) as error:
            raise AttachmentLoadError(404, 'attachment not found') from error
        if not user_id:
            raise AttachmentLoadError(401, 'user not authenticated')
        workspace = attachment.get('workspace_id') or ''
        if not workspace:
            raise AttachmentLoadError(404, 'attachment not found')
        if not self.cache.get(user_id, workspace):
            try:
                self.queries.get_member(parse_uuid(workspace), parse_uuid(user_id))
            except (Exception, CancelledError) as error:
                raise AttachmentLoadError(404, 'attachment not found') from error
            self.cache.set(user_id, workspace)
        return self._visible(workspace, attachment)
