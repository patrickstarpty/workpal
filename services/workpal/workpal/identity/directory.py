"""Current workspace people, without granting access to their business objects."""
from django.contrib.auth import get_user_model
from workpal.contracts import DomainError
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from .service import require_member
from .models import Membership


def list_people(actor, query='', cursor=0, limit=50):
    try:
        valid_query = type(query) is str and len(query) <= 150 and '\x00' not in query
        if valid_query:
            query.encode('utf-8')
    except UnicodeError:
        valid_query = False
    if (not valid_query or type(cursor) is not int or not 0 <= cursor <= MAX_SQLITE_INTEGER
            or type(limit) is not int or not 1 <= limit <= 200):
        raise DomainError('invalid_input', 'Invalid directory fields.', status=400)

    def read():
        require_member(actor, actor.workspace_id)
        members = Membership.objects.filter(workspace_id=actor.workspace_id).values('user_id')
        rows = list(get_user_model().objects.filter(
            pk__in=members, is_active=True, pk__gt=cursor, username__icontains=query
        ).order_by('pk').values('id', 'username')[:limit + 1])
        return dict(items=[dict(user_id=r['id'], username=r['username']) for r in rows[:limit]],
                    next_cursor=rows[limit - 1]['id'] if len(rows) > limit else 0)
    return atomic_write(read)


def read_person(actor, user_id):
    """Read one active current workspace member, or return an empty result."""
    if type(user_id) is not int or not 1 <= user_id <= MAX_SQLITE_INTEGER:
        raise DomainError('invalid_input', 'Invalid directory fields.', status=400)

    def read():
        require_member(actor, actor.workspace_id)
        members = Membership.objects.filter(workspace_id=actor.workspace_id).values('user_id')
        row = get_user_model().objects.filter(
            pk=user_id, pk__in=members, is_active=True
        ).values('id', 'username').first()
        return {'person': {'user_id': row['id'], 'username': row['username']}} if row else {}
    return atomic_write(read)
