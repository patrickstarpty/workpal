"""Original comment/reaction response fields without summary or fold projection."""
from ..infrastructure.go_time import format_timestamp
from ..infrastructure.go_uuid import parse_uuid


def _uuid(row, key):
    value = row.get(key)
    return parse_uuid(value) if value is not None else None


def _time(row, key):
    value = row.get(key)
    return format_timestamp(value) if value is not None else None


def comment_response(row, reactions=None, attachments=None):
    response = dict(id=_uuid(row,'id') or '', issue_id=_uuid(row,'issue_id') or '',
        author_type=row['author_type'], author_id=_uuid(row,'author_id') or '',
        content=row['content'], type=row['type'], parent_id=_uuid(row,'parent_id'),
        created_at=format_timestamp(row.get('created_at')),
        updated_at=format_timestamp(row.get('updated_at')), revision=row['revision'],
        resolved_at=_time(row,'resolved_at'), resolved_by_type=row.get('resolved_by_type'),
        resolved_by_id=_uuid(row,'resolved_by_id'))
    if row.get('source_task_id') is not None:
        response['source_task_id'] = _uuid(row,'source_task_id')
    if row.get('deleted_at') is not None:
        response['deleted_at'] = _time(row,'deleted_at')
    if row.get('quick_action_id') is not None:
        response['quick_action_id'] = _uuid(row,'quick_action_id')
    response['reactions'] = reactions if reactions is not None else []
    response['attachments'] = attachments if attachments is not None else []
    return response


def reaction_response(row, *, added=False):
    response = dict(id=_uuid(row,'id') or '', comment_id=_uuid(row,'comment_id') or '',
        actor_type=row['actor_type'], actor_id=_uuid(row,'actor_id') or '', emoji=row['emoji'],
        created_at=format_timestamp(row.get('created_at')))
    if added and row.get('comment_revision', 0) > 0:
        response['comment_revision'] = row['comment_revision']
    return response
