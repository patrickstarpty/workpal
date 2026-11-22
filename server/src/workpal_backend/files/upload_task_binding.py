"""Bind task-produced uploads only to their authenticated chat run."""
from asyncio import CancelledError
from ..auth.profile_decode import go_trim_space
from ..infrastructure.go_uuid import parse_uuid
from .loader import AttachmentLoadError


def task_upload_binding(queries, workspace_id, task_id, *, actor_source,
                        bound_task_id, uploader_type, uploader_id):
    if actor_source != 'task_token':
        raise AttachmentLoadError(403, 'task_id upload is only available from within an agent task')
    try:
        identity = parse_uuid(task_id)
    except ValueError as error:
        raise AttachmentLoadError(400, 'invalid task_id') from error
    bound = go_trim_space(bound_task_id)
    if not bound or bound.lower() != go_trim_space(task_id).lower():
        raise AttachmentLoadError(403, "task_id must match the request's task token")
    try:
        task = queries.get_task_in_workspace(identity, parse_uuid(workspace_id))
    except (Exception, CancelledError) as error:
        raise AttachmentLoadError(403, 'invalid task_id') from error
    if uploader_type != 'agent' or (task.get('agent_id') or '') != uploader_id:
        raise AttachmentLoadError(403, "task_id upload requires the task's own agent")
    if task.get('chat_session_id') is None:
        raise AttachmentLoadError(400, 'task_id upload requires a chat task')
    return {'task_id':task['id'], 'chat_session_id':task['chat_session_id']}
