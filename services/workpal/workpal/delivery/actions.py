"""Thin closed-schema Registry adapters."""
from django import forms
from workpal.actions.schemas import StructuredField
from workpal.actions.contracts import ActionSpec
from workpal.contracts import SubjectRef, ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work.issue_actions import SNAP, HISTORY, STR, INT
from .artifact_actions import obj, SOURCES, ARTIFACT_VIEW
from . import service
SUBJECT=obj(dict(type=dict(type='string',enum=['issue']),id=dict(type='string',minLength=1,maxLength=19)))
IDS=dict(type='array',maxItems=100,items=dict(type='integer',minimum=1,maximum=MAX_SQLITE_INTEGER-1))
EVIDENCE=dict(type='array',maxItems=100,items=obj(dict(criterion_key=dict(type='string',maxLength=64),artifact_ids=IDS,note=dict(type='string',maxLength=4000)),['criterion_key','artifact_ids']))
class Submit(forms.Form):
    subject=StructuredField(schema=SUBJECT)
    requirements_revision=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER-1)
    summary=forms.CharField(max_length=10000,strip=False)
    limitations=forms.CharField(max_length=20000,strip=False,required=False)
    artifact_ids=StructuredField(schema=IDS,required=False)
    evidence=StructuredField(schema=EVIDENCE,required=False)
    source_refs=StructuredField(schema=SOURCES,required=False)
    def clean(self):
        data=super().clean()
        return {k:v for k,v in data.items() if k in self.data}
class Read(forms.Form):
    delivery_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER-1)
VIEW=obj(dict(id=INT,number=INT,submitted_by=INT,created_at=STR,subject=SUBJECT,source=dict(type='string',enum=['human']),summary=STR,limitations=STR,requirements_snapshot=HISTORY,workflow_snapshot=SNAP,artifacts_snapshot=dict(type='array',items=ARTIFACT_VIEW),evidence=EVIDENCE,sha256=STR))
def unpack(payload): return SubjectRef(**payload['subject']),{k:v for k,v in payload.items() if k!='subject'}
def resolve_submit(actor,payload): return service.prepare(actor,*unpack(payload))[1]
def resolve_read(actor,payload): return [service.ref(service.read(actor,payload['delivery_id'])['id'])]
class List(forms.Form):
    subject=StructuredField(schema=SUBJECT)
    cursor=StructuredField(schema=dict(type='integer',minimum=0,maximum=MAX_SQLITE_INTEGER-1),required=False)
    limit=StructuredField(schema=dict(type='integer',minimum=1,maximum=200),required=False)
    def clean(self):
        data=super().clean()
        return {k:v for k,v in data.items() if k in self.data}
SUMMARY=obj(dict(id=INT,number=INT,subject=SUBJECT,source=STR,submitted_by=INT,created_at=STR,summary=STR,requirements_revision=INT,sha256=STR))
PAGE=obj(dict(items=dict(type='array',items=SUMMARY),next_cursor=dict(type='integer',minimum=0)))
def resolve_list(actor,payload):
    return service.subject_refs(actor,SubjectRef(**payload['subject']))
def register_actions():
    from workpal.actions.registry import register
    def submit(actor,payload,revision):
        data=service.submit(actor,*unpack(payload))
        return ActionResult('completed',[service.ref(data['id'])],data)
    def read(actor,payload,revision):
        data=service.read(actor,payload['delivery_id'])
        return ActionResult('completed',[service.ref(data['id'])],data)
    register(ActionSpec('delivery.submit',Submit,VIEW,submit,resolve_submit,capability='write',mutating=True,audit_fields=('subject','requirements_revision','artifact_ids')))
    register(ActionSpec('delivery.read',Read,VIEW,read,resolve_read,audit_fields=('delivery_id',)))

    def listing(actor,payload,revision):
        data=service.list_deliveries(actor,SubjectRef(**payload['subject']),**{k:v for k,v in payload.items() if k!='subject'})
        return ActionResult('completed',[service.issues.ref(int(payload['subject']['id']))]+[service.ref(item['id']) for item in data['items']],data)
    register(ActionSpec('delivery.list',List,PAGE,listing,resolve_list,audit_fields=('subject','cursor','limit')))
