"""Immutable human decisions; current execution gates live inside the transaction."""
from copy import deepcopy
from django.db.models import F
from workpal.contracts import SubjectRef, ObjectRef, DomainError
from workpal.identity.service import require_member
from workpal.access.service import authorize, register_object
from workpal.storage import atomic_write
from . import service, selection, artifacts
from .models import Delivery, DeliveryCurrent, Review

def ref(pk): return ObjectRef('review', str(pk))
def conflict(code): raise DomainError(code, 'Review target or evidence changed.', status=409)

def prepare(actor, delivery_id, version, decision):
    member = require_member(actor, actor.workspace_id)
    if actor.executor_id is not None:
        raise DomainError('permission_denied', 'Human reviewer required.', status=403)
    service.issues.integer(delivery_id)
    service.issues.integer(version)
    if type(decision) is not dict or set(decision)-{'outcome','reason','source_refs'}: service.issues.fail()
    if decision.get('outcome') not in ('approve','request_changes'): service.issues.fail()
    service.issues.validate_text(decision.get('reason'),4000,True)
    explicit = service.issues.sources(decision.get('source_refs',[]))
    for source in explicit:
        service.issues.validate_text(source.kind,100)
        service.issues.validate_text(source.id,255)
    target = Delivery.objects.filter(pk=delivery_id,workspace_id=actor.workspace_id).first()
    if target is None: raise DomainError('not_found','Delivery unavailable.',status=404)
    if version != target.number: conflict('version_conflict')
    roles = target.workflow_snapshot['definition']['review_policy']['reviewer_roles']
    if member.role not in roles:
        raise DomainError('permission_denied','Reviewer role required.',status=403)
    subject = SubjectRef(target.subject_type,target.subject_id)
    issue = service._subject_issue(actor,subject,'write')
    refs = [service.issues.ref(issue.pk),service.ref(target.pk),
            service.issues.requirement_ref(target.requirements_snapshot['id'])] + explicit
    authorize(actor,'write',refs)
    return target,issue,subject,refs

def view(row):
    return deepcopy(dict(id=row.pk,subject=dict(type=row.delivery.subject_type,id=row.delivery.subject_id),
        delivery_id=row.delivery_id,version=row.version,revision=row.revision,
        delivery_sha256=row.delivery_sha256,requirements_snapshot=row.requirements_snapshot,
        workflow_snapshot=row.workflow_snapshot,decision=dict(outcome=row.outcome,reason=row.reason),
        actor_user_id=row.actor_id,created_at=row.created_at.isoformat()))

def review(actor, delivery_id, version, revision, decision):
    def write():
        service.issues.integer(revision)
        target,issue,subject,refs = prepare(actor,delivery_id,version,decision)
        row = selection.pointer(actor,subject)
        if issue.archived: conflict('issue_archived')
        if row is None or row.current_delivery_id != target.pk: conflict('current_conflict')
        if row.revision != revision: conflict('revision_conflict')
        if decision['outcome'] == 'approve':
            latest = service.issues.read_requirements(actor,issue.pk,issue.current_requirements.number)
            if any(latest[k] != target.requirements_snapshot[k] for k in ('id','number','sha256')):
                conflict('requirements_conflict')
            manifest = {item['id']:item for item in target.artifacts_snapshot}
            for pk,snapshot in manifest.items():
                actual = artifacts.read(actor,pk)
                if any(actual[k] != snapshot[k] for k in ('id','size','sha256')): conflict('evidence_conflict')
            criteria = target.requirements_snapshot['criteria']
            evidence = {item['criterion_key']:item['artifact_ids'] for item in target.evidence}
            if not criteria or any(not evidence.get(c['key']) or not set(evidence[c['key']]) <= set(manifest) for c in criteria):
                conflict('evidence_required')
        if DeliveryCurrent.objects.filter(pk=row.pk,revision=revision,current_delivery=target).update(revision=F('revision')+1) != 1:
            conflict('revision_conflict')
        saved = Review.objects.create(workspace_id=actor.workspace_id,delivery=target,current=row,
            version=version,revision=revision+1,delivery_sha256=target.sha256,
            requirements_snapshot=deepcopy(target.requirements_snapshot),workflow_snapshot=deepcopy(target.workflow_snapshot),
            outcome=decision['outcome'],reason=decision['reason'],actor_id=actor.user_id)
        register_object(actor.workspace_id,ref(saved.pk),refs)
        return view(saved)
    return atomic_write(write)

def read(actor,review_id):
    service.issues.integer(review_id)
    require_member(actor,actor.workspace_id)
    row = Review.objects.select_related('delivery').filter(pk=review_id,workspace_id=actor.workspace_id).only(
        'id','delivery_id','version','revision','delivery_sha256','requirements_snapshot',
        'workflow_snapshot','outcome','reason','actor_id','created_at',
        'delivery__subject_type','delivery__subject_id').first()
    if row is None: raise DomainError('not_found','Review unavailable.',status=404)
    authorize(actor,'read',[ref(row.pk)])
    return view(row)


def list_reviews(actor, subject, cursor=0, limit=50):
    from workpal.storage import MAX_SQLITE_INTEGER
    if type(cursor) is not int or not 0 <= cursor < MAX_SQLITE_INTEGER:
        service.issues.fail()
    if type(limit) is not int or not 1 <= limit <= 200:
        service.issues.fail()
    service.subject_refs(actor, subject)
    rows = Review.objects.filter(workspace_id=actor.workspace_id,
        delivery__workspace_id=actor.workspace_id, delivery__subject_type=subject.type,
        delivery__subject_id=subject.id, id__gt=cursor).order_by('id').values(
        'id', 'delivery_id', 'version', 'revision', 'delivery_sha256',
        'requirements_snapshot__number', 'outcome', 'reason', 'actor_id', 'created_at')
    items = []
    for row in rows.iterator():
        try:
            authorize(actor, 'read', [ref(row['id'])])
        except DomainError as error:
            if error.status in (403, 404):
                continue
            raise
        if len(items) == limit:
            return dict(items=items, next_cursor=items[-1]['id'])
        items.append(dict(id=row['id'], subject=dict(type=subject.type, id=subject.id),
            delivery_id=row['delivery_id'], version=row['version'], revision=row['revision'],
            delivery_sha256=row['delivery_sha256'],
            requirements_revision=row['requirements_snapshot__number'],
            decision=dict(outcome=row['outcome'], reason=row['reason']),
            actor_user_id=row['actor_id'], created_at=row['created_at'].isoformat()))
    return dict(items=items, next_cursor=0)
