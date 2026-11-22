"""Issue lookup and visibility after trusted HTTP identity resolution."""
import re
from asyncio import CancelledError

from ..infrastructure.go_uuid import parse_uuid
from ..infrastructure.request_cancellation import is_query_cancellation
from ..realtime.origins import _equal_fold


class IssueLoadError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


def split_identifier(identity):
    prefix, separator, digits = identity.rpartition('-')
    if not separator or not prefix or not digits:
        return None
    number = 0
    for char in digits:
        if not '0' <= char <= '9':
            return None
        number = number * 10 + ord(char) - ord('0')
        if number > 2147483647:
            return None
    return (prefix, number) if number > 0 else None


def issue_prefix(workspace):
    return workspace.get('issue_prefix') or re.sub('[^a-zA-Z]', '', workspace['name']).upper()[:3] or 'WS'


class IssueLoader:
    def __init__(self, queries, *, hidden_projects, request_error=lambda: None):
        self.queries = queries
        self.hidden_projects = hidden_projects
        self.request_error = request_error

    def _cancel(self, error):
        if is_query_cancellation(self.request_error(), error):
            raise IssueLoadError(499, '') from error

    def _by_identifier(self, identity, workspace):
        parts = split_identifier(identity)
        if parts is None:
            return None
        try:
            workspace = parse_uuid(workspace)
        except ValueError:
            return None
        try:
            stored = self.queries.get_workspace(workspace)
            prefix = issue_prefix(stored)
            if not prefix or not _equal_fold(parts[0], prefix):
                return None
            return self.queries.get_issue_by_number(workspace, parts[1])
        except (Exception, CancelledError) as error:
            self._cancel(error)
            return None

    def for_user(self, identity, user, workspace):
        if not user:
            raise IssueLoadError(401, 'user not authenticated')
        if not workspace:
            raise IssueLoadError(400, 'workspace_id is required')
        issue = self._by_identifier(identity, workspace)
        if issue is None:
            try:
                issue_id = parse_uuid(identity)
            except ValueError as error:
                raise IssueLoadError(404, 'issue not found') from error
            try:
                workspace_id = parse_uuid(workspace)
            except ValueError as error:
                raise IssueLoadError(400, 'invalid workspace_id') from error
            try:
                issue = self.queries.get_issue_in_workspace(issue_id, workspace_id)
            except (Exception, CancelledError) as error:
                self._cancel(error)
                raise IssueLoadError(404, 'issue not found') from error
        project = issue.get('project_id')
        if project is not None:
            try:
                hidden = self.hidden_projects(workspace)
            except (Exception, CancelledError) as error:
                self._cancel(error)
                raise IssueLoadError(500, 'failed to resolve project access') from error
            if not hidden.can_see_project(project):
                raise IssueLoadError(404, 'issue not found')
        return issue
