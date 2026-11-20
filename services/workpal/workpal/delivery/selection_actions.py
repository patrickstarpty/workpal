"""Thin Registry adapters for explicit selection."""
from django import forms
from workpal.actions.schemas import StructuredField
from workpal.actions.contracts import ActionSpec
from workpal.contracts import SubjectRef, ObjectRef, ActionResult
from .actions import SUBJECT, List, resolve_list
from workpal.storage import MAX_SQLITE_INTEGER
from .artifact_actions import obj
from . import selection, service
from .models import DeliverySelection
class Current(forms.Form):
    subject=StructuredField(schema=SUBJECT)
class Select(forms.Form):
    delivery_id=StructuredField(schema=dict(type="integer",minimum=1,maximum=MAX_SQLITE_INTEGER-1))
    reason=forms.CharField(max_length=4000,strip=False)
VIEW=obj(dict(subject=SUBJECT,revision=dict(type='integer',minimum=1),current_delivery_id=dict(type='integer',minimum=0),current_delivery_number=dict(type='integer',minimum=0)))
def refs(data):
    result=[service.issues.ref(int(data['subject']['id']))]
    if data['current_delivery_id']: result.append(service.ref(data['current_delivery_id']))
    return result

def register_actions():
    from workpal.actions.registry import register
    def read(actor,payload,revision):
        data=selection.current(actor,SubjectRef(**payload['subject']))
        return ActionResult('completed',refs(data),data)
    def resolve_read(actor,payload):
        return refs(selection.current(actor,SubjectRef(**payload['subject'])))
    def resolve_select(actor,payload):
        return selection.prepare(actor,**payload)[4]
    def select(actor,payload,revision):
        data=selection.select_current(actor,revision=revision,**payload)
        event=DeliverySelection.objects.get(current__workspace_id=actor.workspace_id,current__subject_type=data['subject']['type'],current__subject_id=data['subject']['id'],revision=data['revision'])
        return ActionResult('completed',refs(data)+[ObjectRef('delivery_selection',str(event.pk))],data)
    def listing(actor,payload,revision):
        data=selection.list_history(actor,SubjectRef(**payload['subject']),
            **{k:v for k,v in payload.items() if k!='subject'})
        return ActionResult('completed',[service.issues.ref(int(payload['subject']['id']))]+
            [ObjectRef('delivery_selection',str(item['id'])) for item in data['items']],data)
    integer=dict(type='integer',minimum=0)
    item=obj(dict(id=integer,subject=SUBJECT,revision=integer,
        before_delivery_id=integer,before_delivery_number=integer,
        after_delivery_id=integer,after_delivery_number=integer,
        actor_user_id=integer,reason=dict(type='string'),created_at=dict(type='string')))
    page=obj(dict(items=dict(type='array',items=item),next_cursor=integer))
    register(ActionSpec('delivery.selections.list',List,page,listing,resolve_list,
        audit_fields=('subject','cursor','limit')))
    register(ActionSpec('delivery.current.read',Current,VIEW,read,resolve_read,audit_fields=('subject',)))
    register(ActionSpec('delivery.select_current',Select,VIEW,select,resolve_select,capability='write',mutating=True,revision_required=True,audit_fields=('delivery_id',)))
