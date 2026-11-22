"""Capture trusted request attribution for transaction-local wakeup settings."""
from asyncio import CancelledError
from .actor import resolve_actor
from ..infrastructure.go_uuid import parse_uuid


def capture_wakeup_actor(queries, user_id, workspace_id, *, cached=None,
                         actor_source='', agent_id='', task_id=''):
    if cached is not None:
        return cached
    def resolve():
        return resolve_actor(queries, user_id, workspace_id, actor_source=actor_source,
                             agent_id=agent_id, task_id=task_id)
    kind, identity = resolve()
    source = ''
    # The original source resolver independently resolves the actor. Keep its
    # second lookup: a task may disappear between attribution and source lookup.
    if resolve()[0] == 'agent' and task_id:
        try:
            task = queries.get_task(parse_uuid(task_id))
            source = task.get('id') or ''
        except (Exception, CancelledError):
            pass
    return kind, identity, source
