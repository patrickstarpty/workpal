"""Chat ownership, current agent access, and public projection gates."""
from asyncio import CancelledError
from ..agents.access import can_access_private_agent
from ..auth.actor import resolve_actor
from ..infrastructure.go_uuid import parse_uuid


class ChatAccessError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def _identity(value, field):
    try:
        return parse_uuid(value)
    except ValueError as error:
        raise ChatAccessError(400, 'invalid ' + field) from error


def load_session_for_user(queries, user_id, workspace_id, session_id):
    session = _identity(session_id, 'chat session id')
    workspace = _identity(workspace_id, 'workspace id')
    try:
        row = queries.get_chat_session_in_workspace(session, workspace)
    except (Exception, CancelledError) as error:
        raise ChatAccessError(404, 'chat session not found') from error
    if (row.get('creator_id') or '') != user_id:
        raise ChatAccessError(403, 'not your chat session')
    return row


def session_for_user(queries, user_id, workspace_id, session_id, *,
                     actor_source='', agent_id='', task_id=''):
    session = load_session_for_user(queries, user_id, workspace_id, session_id)
    try:
        agent = queries.get_agent(session['agent_id'])
    except (Exception, CancelledError) as error:
        raise ChatAccessError(404, 'agent not found') from error
    actor_type, actor_id = resolve_actor(queries, user_id, workspace_id,
        actor_source=actor_source, agent_id=agent_id, task_id=task_id)
    if not can_access_private_agent(queries, agent, actor_type, actor_id, workspace_id):
        raise ChatAccessError(403, 'you do not have access to this agent')
    return session


def public_session_for_user(queries, user_id, workspace_id, session_id, **actor):
    session = session_for_user(queries, user_id, workspace_id, session_id, **actor)
    try:
        queries.get_public_chat_session_in_workspace(session['id'], session['workspace_id'])
    except (Exception, CancelledError) as error:
        raise ChatAccessError(404, 'chat session not found') from error
    return session
