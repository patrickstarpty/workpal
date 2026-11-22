"""Go actor resolution after authentication has stripped untrusted headers.

The legacy ID-pair fallback is not an authentication or impersonation boundary.
Only the authentication layer may supply task_token actor source.
"""
from asyncio import CancelledError
from ..infrastructure.go_uuid import parse_uuid


def resolve_actor(queries, user_id, workspace_id, *, actor_source='', agent_id='', task_id=''):
    if actor_source == 'task_token':
        return 'agent', agent_id
    member = 'member', user_id
    if not agent_id or not task_id:
        return member
    try:
        agent_uuid = parse_uuid(agent_id)
    except ValueError:
        return member
    try:
        agent = queries.get_agent(agent_uuid)
    except (Exception, CancelledError):
        return member
    if (agent.get('workspace_id') or '') != workspace_id:
        return member
    try:
        task_uuid = parse_uuid(task_id)
    except ValueError:
        return member
    try:
        task = queries.get_task(task_uuid)
    except (Exception, CancelledError):
        return member
    if task.get('agent_id') != agent_id:
        return member
    return 'agent', agent_id
