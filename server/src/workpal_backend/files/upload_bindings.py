"""Validate workspace upload associations before writing object bytes."""
from asyncio import CancelledError
from ..auth.actor import resolve_actor
from ..chat.access import public_session_for_user, ChatAccessError
from ..infrastructure.go_uuid import parse_uuid
from ..infrastructure.query_errors import NoRows
from ..infrastructure.request_cancellation import is_query_cancellation
from .loader import AttachmentLoadError
from .upload_task_binding import task_upload_binding


def _identity(value, field):
    try:
        return parse_uuid(value)
    except ValueError as error:
        raise AttachmentLoadError(400, 'invalid ' + field) from error


class UploadBinding(dict):
    """SQL values plus the raw resolved actor used by post-commit events."""
    def __init__(self, values, uploader):
        super().__init__(values)
        self.uploader = uploader


class UploadBindings:
    def __init__(self, queries, *, hidden_projects, request_error=lambda: None):
        self.queries = queries
        self.hidden_projects = hidden_projects
        self.request_error = request_error

    def _hidden(self, workspace):
        try:
            return self.hidden_projects(workspace)
        except (Exception, CancelledError) as error:
            if is_query_cancellation(self.request_error(), error):
                raise AttachmentLoadError(499, '') from error
            raise AttachmentLoadError(500, 'failed to resolve project access') from error

    def _project(self, workspace, project, field):
        if project is not None and not self._hidden(workspace).can_see_project(project):
            raise AttachmentLoadError(403, 'invalid ' + field)

    def _issue(self, workspace, issue):
        if issue is None:
            return
        hidden = self._hidden(workspace)
        if hidden.empty():
            return
        try:
            project = self.queries.issue_project(issue)
        except NoRows:
            return
        except (Exception, CancelledError) as error:
            raise AttachmentLoadError(500, 'failed to resolve project access') from error
        if not hidden.can_see_project(project):
            raise AttachmentLoadError(403, 'invalid comment_id')

    def resolve(self, user_id, workspace_id, values, *, actor_source='', agent_id='', task_id=''):
        try:
            workspace = parse_uuid(workspace_id)
            self.queries.get_member(workspace, parse_uuid(user_id))
        except (Exception, CancelledError) as error:
            raise AttachmentLoadError(403, 'not a member of this workspace') from error
        actor = dict(actor_source=actor_source, agent_id=agent_id, task_id=task_id)
        uploader_type, uploader_id = resolve_actor(self.queries, user_id, workspace_id, **actor)
        try:
            uploader_uuid = parse_uuid(uploader_id)
        except ValueError:
            uploader_uuid = None
        result = dict(workspace_id=workspace, uploader_type=uploader_type, uploader_id=uploader_uuid)
        if value := values.get('issue_id', ''):
            identity = _identity(value, 'issue_id')
            try:
                issue = self.queries.get_issue_in_workspace(identity, workspace)
            except (Exception, CancelledError) as error:
                raise AttachmentLoadError(403, 'invalid issue_id') from error
            self._project(workspace_id, issue.get('project_id'), 'issue_id')
            result['issue_id'] = issue['id']
        if value := values.get('comment_id', ''):
            identity = _identity(value, 'comment_id')
            try:
                comment = self.queries.get_comment(identity)
            except (Exception, CancelledError) as error:
                raise AttachmentLoadError(403, 'invalid comment_id') from error
            if (comment.get('workspace_id') or '') != workspace_id or comment.get('deleted_at') is not None:
                raise AttachmentLoadError(403, 'invalid comment_id')
            self._issue(workspace_id, comment.get('issue_id'))
            result['comment_id'] = comment['id']
        if value := values.get('chat_session_id', ''):
            try:
                session = public_session_for_user(self.queries, user_id, workspace_id, value, **actor)
            except ChatAccessError as error:
                raise AttachmentLoadError(error.status, error.message) from error
            result['chat_session_id'] = session['id']
        if value := values.get('task_id', ''):
            result.update(task_upload_binding(self.queries, workspace_id, value,
                actor_source=actor_source, bound_task_id=task_id,
                uploader_type=uploader_type, uploader_id=uploader_id))
        return UploadBinding(result, (uploader_type, uploader_id))
