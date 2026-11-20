"""Immutable submissions and authorized history behind a small Interface."""
import hashlib
import json
import re
from copy import deepcopy
from dataclasses import asdict
from workpal.contracts import SubjectRef, ObjectRef, DomainError
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from workpal.access.service import authorize, register_object
from workpal.work import issues
from . import artifacts
from .models import Delivery, DeliveryArtifact

def ref(pk): return ObjectRef('delivery', str(pk))
def _subject_issue(actor, subject, capability='read'):
    if (not isinstance(subject, SubjectRef) or subject.type != 'issue'
            or type(subject.id) is not str or not 1 <= len(subject.id) <= 19
            or not re.fullmatch(r'[1-9][0-9]*', subject.id)): issues.fail()
    return issues.selected(actor, int(subject.id), capability)

def subject_refs(actor, subject):
    """Resolve subject authorization without scanning its Delivery history."""
    return [issues.ref(_subject_issue(actor, subject).pk)]

def prepare(actor, subject, submission):
    if actor.executor_id is not None:
        raise DomainError('permission_denied','Human actor required.',status=403)
    if type(submission) is not dict or set(submission)-{'requirements_revision','summary','limitations','artifact_ids','evidence','source_refs'}: issues.fail()
    row=_subject_issue(actor,subject,'write')
    issues.validate_text(submission.get('summary'),10000,True)
    issues.validate_text(submission.get('limitations',''),20000)
    req=issues.read_requirements(actor,row.pk,submission.get('requirements_revision'))
    ids=submission.get('artifact_ids',[])
    def valid_ids(values):
        if type(values) is not list or len(values)>100: issues.fail()
        for value in values: issues.integer(value)
        if len(set(values))!=len(values): issues.fail()
    valid_ids(ids)
    snapshots=[artifacts.read(actor,i) for i in ids]
    evidence=submission.get('evidence',[])
    if type(evidence) is not list or len(evidence)>100: issues.fail()
    seen=set(); normalized=[]
    for item in evidence:
        if type(item) is not dict or set(item)-{'criterion_key','artifact_ids','note'} or not {'criterion_key','artifact_ids'}<=set(item): issues.fail()
        key=item['criterion_key']
        if type(key) is not str or key in seen or key not in {c['key'] for c in req['criteria']}: issues.fail()
        seen.add(key); valid_ids(item['artifact_ids'])
        if not set(item['artifact_ids'])<=set(ids): issues.fail()
        issues.validate_text(item.get('note',''),4000)
        normalized.append(dict(item,note=item.get('note','')))
    explicit_refs = issues.sources(submission.get('source_refs', []))
    for source in explicit_refs:
        issues.validate_text(source.kind, 100)
        issues.validate_text(source.id, 255)
    refs=[issues.ref(row.pk),issues.requirement_ref(req['id'])]+[artifacts.artifact_ref(i) for i in ids]+explicit_refs
    authorize(actor,'write',refs)
    data=dict(subject=asdict(subject),source='human',summary=submission['summary'],limitations=submission.get('limitations',''),requirements_snapshot=req,workflow_snapshot=row.workflow_snapshot,artifacts_snapshot=snapshots,evidence=normalized)
    return row,refs,data

def view(row):
    return deepcopy(dict(id=row.pk,number=row.number,submitted_by=row.submitted_by_id,created_at=row.created_at.isoformat(),subject=dict(type=row.subject_type,id=row.subject_id),**{k:getattr(row,k) for k in ('source','summary','limitations','requirements_snapshot','workflow_snapshot','artifacts_snapshot','evidence','sha256')}))

def submit(actor,subject,submission):
    def write():
        issue,refs,data=prepare(actor,subject,submission)
        if issue.archived: raise DomainError('issue_archived','Issue archived.',status=409)
        previous=Delivery.objects.filter(workspace_id=actor.workspace_id,subject_type=subject.type,subject_id=subject.id).order_by('-number').first()
        digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf8')).hexdigest()
        values={k:v for k,v in data.items() if k!='subject'}
        row=Delivery.objects.create(workspace_id=actor.workspace_id,subject_type=subject.type,subject_id=subject.id,number=previous.number+1 if previous else 1,submitted_by_id=actor.user_id,sha256=digest,**values)
        register_object(actor.workspace_id,ref(row.pk),refs)
        for pk in submission.get('artifact_ids',[]): DeliveryArtifact.objects.create(delivery=row,artifact_id=pk)
        return view(row)
    return atomic_write(write)

def read(actor,delivery_id):
    issues.integer(delivery_id)
    from workpal.identity.service import require_member
    require_member(actor,actor.workspace_id)
    row=Delivery.objects.filter(pk=delivery_id,workspace_id=actor.workspace_id).first()
    if row is None: raise DomainError('not_found','Delivery unavailable.',status=404)
    authorize(actor,'read',[ref(row.pk)])
    return view(row)

def list_deliveries(actor, subject, cursor=0, limit=50):
    if type(cursor) is not int or not 0 <= cursor < MAX_SQLITE_INTEGER:
        issues.fail()
    if type(limit) is not int or not 1 <= limit <= 200:
        issues.fail()
    subject_refs(actor, subject)
    rows = Delivery.objects.filter(workspace_id=actor.workspace_id,
        subject_type=subject.type, subject_id=subject.id, id__gt=cursor).order_by('id').values(
        'id', 'number', 'source', 'submitted_by_id', 'created_at', 'summary',
        'requirements_snapshot__number', 'sha256')
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
        items.append(dict(id=row['id'], number=row['number'], subject=asdict(subject),
            source=row['source'], submitted_by=row['submitted_by_id'],
            created_at=row['created_at'].isoformat(), summary=row['summary'],
            requirements_revision=row['requirements_snapshot__number'], sha256=row['sha256']))
    return dict(items=items, next_cursor=0)
