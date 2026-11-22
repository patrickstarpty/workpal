"""Canonical agent visibility; invocation authorization is a separate policy."""
from asyncio import CancelledError
from ..infrastructure.go_uuid import parse_uuid


def member_hits_invocation_targets(targets, user_id):
    for target in targets:
        if target['target_type'] == 'workspace':
            return True
        if target['target_type'] == 'member' and (target.get('target_id') or '') == user_id:
            return True
    return False


def member_allowed_to_view_agent(agent, targets, user_id, role):
    if role in ('owner', 'admin') or (agent.get('owner_id') or '') == user_id:
        return True
    return agent['permission_mode'] == 'public_to' and member_hits_invocation_targets(targets, user_id)


def can_access_private_agent(queries, agent, actor_type, actor_id, workspace_id):
    if actor_type == 'agent' or (agent.get('owner_id') or '') == actor_id:
        return True
    try:
        member = queries.get_member(parse_uuid(workspace_id), parse_uuid(actor_id))
    except (Exception, CancelledError):
        return False
    if member['role'] in ('owner', 'admin'):
        return True
    if agent['permission_mode'] != 'public_to':
        return False
    try:
        targets = queries.list_agent_invocation_targets(agent['id'])
    except (Exception, CancelledError):
        return False
    return member_hits_invocation_targets(targets, actor_id)
