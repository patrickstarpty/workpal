"""Thin closed Registry adapters for human review."""
from django import forms
from workpal.actions.schemas import StructuredField
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult, SubjectRef
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work.issue_actions import INT, STR, HISTORY, SNAP
from .actions import SUBJECT, List, resolve_list
from .artifact_actions import obj, SOURCES
from . import review
DECISION=obj(dict(outcome=dict(type='string',enum=['approve','request_changes']),reason=dict(type='string',minLength=1,maxLength=4000),source_refs=SOURCES),['outcome','reason'])
POSITIVE_ID=dict(type='integer',minimum=1,maximum=MAX_SQLITE_INTEGER-1)
class Decide(forms.Form):
    delivery_id=StructuredField(schema=POSITIVE_ID)
    version=StructuredField(schema=POSITIVE_ID)
    decision=StructuredField(schema=DECISION)
class Read(forms.Form):
    review_id=StructuredField(schema=POSITIVE_ID)
VIEW=obj(dict(id=INT,subject=SUBJECT,delivery_id=INT,version=INT,revision=INT,delivery_sha256=STR,
    requirements_snapshot=HISTORY,workflow_snapshot=SNAP,decision=obj(dict(outcome=STR,reason=STR)),actor_user_id=INT,created_at=STR))
def register_actions():
    from workpal.actions.registry import register
    def resolve(actor,payload): return review.prepare(actor,**payload)[3]
    def decide(actor,payload,revision):
        data=review.review(actor,revision=revision,**payload)
        return ActionResult('completed',[review.ref(data['id'])],data)
    def resolve_read(actor,payload): return [review.ref(review.read(actor,**payload)['id'])]
    def read(actor,payload,revision):
        data=review.read(actor,**payload)
        return ActionResult('completed',[review.ref(data['id'])],data)
    register(ActionSpec('delivery.review',Decide,VIEW,decide,resolve,capability='write',mutating=True,revision_required=True,audit_fields=('delivery_id','version')))
    register(ActionSpec('review.read',Read,VIEW,read,resolve_read,audit_fields=('review_id',)))

    def listing(actor,payload,revision):
        data=review.list_reviews(actor,SubjectRef(**payload['subject']),**{k:v for k,v in payload.items() if k!='subject'})
        return ActionResult('completed',[review.service.issues.ref(int(payload['subject']['id']))]+[review.ref(item['id']) for item in data['items']],data)
    summary=obj(dict(id=INT,subject=SUBJECT,delivery_id=INT,version=INT,revision=INT,delivery_sha256=STR,
        requirements_revision=INT,decision=obj(dict(outcome=STR,reason=STR)),actor_user_id=INT,created_at=STR))
    page=obj(dict(items=dict(type='array',items=summary),next_cursor=dict(type='integer',minimum=0)))
    register(ActionSpec('review.list',List,page,listing,resolve_list,audit_fields=('subject','cursor','limit')))
