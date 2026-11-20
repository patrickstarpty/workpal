"""Explicit human selection; immutable provenance behind two small Interfaces."""
from dataclasses import asdict
from workpal.contracts import SubjectRef, ObjectRef, DomainError
from workpal.access.service import authorize, register_object
from workpal.storage import atomic_write
from . import service
from .models import Delivery, DeliveryCurrent, DeliverySelection

def pointer(actor, subject):
    return DeliveryCurrent.objects.filter(workspace_id=actor.workspace_id,
        subject_type=subject.type,subject_id=subject.id).select_related('current_delivery').only(
        'id','workspace_id','subject_type','subject_id','revision','current_delivery_id',
        'current_delivery__number').first()

def view(subject, row):
    return dict(subject=asdict(subject), revision=row.revision if row else 1,
        current_delivery_id=row.current_delivery_id if row else 0,
        current_delivery_number=row.current_delivery.number if row else 0)

def current(actor, subject):
    service._subject_issue(actor,subject)
    row=pointer(actor,subject)
    if row: authorize(actor,'read',[service.ref(row.current_delivery_id)])
    return view(subject,row)

def prepare(actor, delivery_id, reason):
    if actor.executor_id is not None:
        raise DomainError('permission_denied','Human actor required.',status=403)
    service.issues.integer(delivery_id)
    service.issues.validate_text(reason,4000,True)
    target=Delivery.objects.filter(pk=delivery_id,workspace_id=actor.workspace_id).only(
        'id','workspace_id','subject_type','subject_id','number').first()
    if target is None: raise DomainError('not_found','Delivery unavailable.',status=404)
    subject=SubjectRef(target.subject_type,target.subject_id)
    issue=service._subject_issue(actor,subject,'write')
    row=pointer(actor,subject)
    refs=[service.issues.ref(issue.pk),service.ref(target.pk)]
    if row: refs.append(service.ref(row.current_delivery_id))
    authorize(actor,'write',refs)
    return subject,issue,target,row,refs

def select_current(actor, delivery_id, revision, reason):
    def write():
        service.issues.integer(revision)
        subject,issue,target,row,refs=prepare(actor,delivery_id,reason)
        if issue.archived: raise DomainError('issue_archived','Issue archived.',status=409)
        if revision != (row.revision if row else 1):
            raise DomainError('revision_conflict','Revision changed.',status=409)
        before=row.current_delivery_id if row else None
        if row:
            row.current_delivery=target; row.revision+=1
            row.save(update_fields=['current_delivery','revision'])
        else:
            row=DeliveryCurrent.objects.create(workspace_id=actor.workspace_id,subject_type=subject.type,subject_id=subject.id,current_delivery=target,revision=2)
        event=DeliverySelection.objects.create(current=row,before_delivery_id=before,after_delivery=target,revision=row.revision,actor_id=actor.user_id,reason=reason)
        register_object(actor.workspace_id,ObjectRef('delivery_selection',str(event.pk)),refs)
        return view(subject,row)
    return atomic_write(write)


def list_history(actor, subject, cursor=0, limit=50):
    from workpal.storage import MAX_SQLITE_INTEGER
    if type(cursor) is not int or not 0 <= cursor < MAX_SQLITE_INTEGER:
        service.issues.fail()
    if type(limit) is not int or not 1 <= limit <= 200:
        service.issues.fail()
    service.subject_refs(actor, subject)
    rows = DeliverySelection.objects.filter(current__workspace_id=actor.workspace_id,
        current__subject_type=subject.type, current__subject_id=subject.id,
        id__gt=cursor).order_by('id').values('id', 'revision', 'before_delivery_id',
        'before_delivery__number', 'after_delivery_id', 'after_delivery__number',
        'actor_id', 'reason', 'created_at')
    items = []
    for row in rows.iterator():
        try:
            authorize(actor, 'read', [ObjectRef('delivery_selection', str(row['id']))])
        except DomainError as error:
            if error.status in (403, 404):
                continue
            raise
        if len(items) == limit:
            return dict(items=items, next_cursor=items[-1]['id'])
        items.append(dict(id=row['id'], subject=asdict(subject), revision=row['revision'],
            before_delivery_id=row['before_delivery_id'] or 0,
            before_delivery_number=row['before_delivery__number'] or 0,
            after_delivery_id=row['after_delivery_id'],
            after_delivery_number=row['after_delivery__number'],
            actor_user_id=row['actor_id'], reason=row['reason'],
            created_at=row['created_at'].isoformat()))
    return dict(items=items, next_cursor=0)
