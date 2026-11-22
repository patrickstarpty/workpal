"""Canonical project visibility for already-resolved request actors.

The HTTP authentication layer owns actor resolution and trusted task identity.
Every returned set remains scoped to the provided canonical workspace.
"""
from .access import Hidden, for_member, for_principals, run_principals
from ..infrastructure.go_uuid import parse_uuid
from ..infrastructure.query_errors import NoRows


def hidden_for_agent_run(queries, workspace, agent_id, task_id):
    private = queries.list_private_project_ids(workspace)
    if not private:
        return Hidden()
    try:
        agent = parse_uuid(agent_id)
        task = parse_uuid(task_id)
    except ValueError:
        return for_principals(queries, workspace)
    try:
        run = queries.get_task(task)
    except NoRows:
        return for_principals(queries, workspace)
    try:
        agent_row = queries.get_agent(agent)
    except NoRows:
        return for_principals(queries, workspace)
    return for_principals(queries, workspace, *run_principals(run, agent_row.get('owner_id')))


def hidden_for_request(queries, workspace_id, user_id, actor_type, actor_id, *, task_id='', context_member=None):
    workspace = parse_uuid(workspace_id)
    if actor_type == 'agent':
        return hidden_for_agent_run(queries, workspace, actor_id, task_id)
    try:
        user = parse_uuid(user_id)
    except ValueError:
        return for_principals(queries, workspace)
    if (context_member is not None and context_member['workspace_id'] == workspace and
            context_member['user_id'] == user):
        return for_member(queries, workspace, user)
    return for_principals(queries, workspace, user)
