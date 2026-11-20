"""Authorized, closed projections of recorded Issue business history."""
from uuid import UUID
from datetime import datetime
from django.core import signing
from django.db.models import Q
from workpal.contracts import ObjectRef, DomainError
from workpal.access.service import authorize
from workpal.work import issues
from workpal.collaboration import service as collaboration
from .models import AuditEvent

ISSUE_ACTIONS = frozenset('issue.' + name for name in (
    'create', 'update', 'archive', 'restore', 'transition',
    'dependency.add', 'dependency.remove', 'set_parent'))
COMMENT_ACTIONS = frozenset('comment.' + name for name in ('create', 'update', 'remove', 'restore'))
SALT = 'workpal.issue.activity.v1'

def invalid():
    raise DomainError('invalid_input', 'Invalid activity query.')

def list_issue_activity(actor, issue_id, cursor='', limit=50):
    issues.integer(issue_id)
    if type(limit) is not int or not 1 <= limit <= 200: invalid()
    if type(cursor) is not str or len(cursor) > 2048: invalid()
    position = None
    if cursor:
        try:
            value = signing.loads(cursor, salt=SALT)
            if type(value) is not list or len(value) != 4: invalid()
            if type(value[0]) is not int or type(value[1]) is not int: invalid()
            if value[:2] != [actor.workspace_id, issue_id]: invalid()
            if type(value[2]) is not str or type(value[3]) is not str: invalid()
            stamp = datetime.fromisoformat(value[2]); uid = UUID(value[3])
            if stamp.tzinfo is None: invalid()
            position = (stamp, uid)
        except (signing.BadSignature, ValueError, TypeError, KeyError): invalid()
    issues.selected(actor, issue_id)
    subject = issues.ref(issue_id)
    visible = []
    events = AuditEvent.objects.filter(workspace_id=actor.workspace_id, outcome='completed',
                                      action_id__in=ISSUE_ACTIONS | COMMENT_ACTIONS)
    if position:
        events = events.filter(Q(created_at__gt=position[0]) | Q(created_at=position[0], id__gt=position[1]))
    # Read bounded batches without loading audit request bodies or caching the
    # workspace's entire history. The visible-item limit still follows authorization.
    events = events.only('id', 'actor_id', 'action_id', 'object_refs', 'scope_refs', 'created_at')
    for event in events.order_by('created_at', 'id').iterator(chunk_size=200):
        outputs = [ObjectRef(**ref) for ref in event.object_refs]
        scopes = [ObjectRef(**ref) for ref in event.scope_refs]
        try:
            if event.action_id in ISSUE_ACTIONS:
                if not outputs or outputs[0] != subject: continue
            else:
                if not outputs or outputs[0].kind != 'comment': continue
                if collaboration.read(actor, int(outputs[0].id))['issue_id'] != issue_id: continue
            authorize(actor, 'read', scopes + outputs)
        except DomainError as error:
            if error.status in (403, 404): continue
            raise
        visible.append((event, outputs, scopes))
        if len(visible) > limit: break
    page = visible[:limit]
    refs = list(dict.fromkeys([subject] + [ref for _, outputs, scopes in page for ref in scopes + outputs]))
    items = [dict(id=str(event.id), action_id=event.action_id, actor_user_id=event.actor_id,
                  created_at=event.created_at.isoformat(), object_refs=[dict(kind=r.kind,id=r.id) for r in outputs]) for event, outputs, _ in page]
    next_cursor = ''
    if len(visible) > limit:
        last = page[-1][0]
        next_cursor = signing.dumps([actor.workspace_id, issue_id, last.created_at.isoformat(), str(last.id)], salt=SALT)
    return dict(items=items, next_cursor=next_cursor), refs
