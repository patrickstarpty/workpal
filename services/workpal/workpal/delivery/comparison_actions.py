"""Closed Registry adapter for Delivery comparison."""
from django import forms
from workpal.actions.schemas import StructuredField
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work.issue_actions import CRITERIA, STR, INT
from .actions import SUBJECT, EVIDENCE
from .artifact_actions import obj, ARTIFACT_VIEW
from . import comparison
ID = dict(type='integer', minimum=1, maximum=MAX_SQLITE_INTEGER-1)
class Compare(forms.Form):
    before_delivery_id = StructuredField(schema=ID)
    after_delivery_id = StructuredField(schema=ID)

def collection(item, key, identity):
    array = lambda schema: dict(type='array', maxItems=100, items=schema)
    return obj(dict(added=array(item), removed=array(item),
        changed=array(obj({key: identity, 'before': item, 'after': item})),
        before_order=array(identity), after_order=array(identity)))
HEADER = obj(dict(id=ID, number=INT, sha256=STR, requirements_revision=INT,
    requirements_sha256=STR, workflow_sha256=STR))
VIEW = obj(dict(subject=SUBJECT, before=HEADER, after=HEADER,
    text_changes=dict(type='array', maxItems=4, items=obj(dict(field=dict(type='string', enum=['summary','limitations','requirements.title','requirements.description']), before=STR, after=STR))),
    criteria=collection(CRITERIA['items'], 'key', STR),
    artifacts=collection(ARTIFACT_VIEW, 'id', ID),
    evidence=collection(EVIDENCE['items'], 'criterion_key', STR),
    workflow_changed=dict(type='boolean')))

def register_actions():
    from workpal.actions.registry import register
    def resolve(actor, payload):
        return comparison.resolve(actor, **payload)
    def handle(actor, payload, revision):
        data = comparison.compare(actor, **payload)
        from . import service
        refs = [service.issues.ref(int(data['subject']['id']))]
        refs += list(dict.fromkeys(service.ref(data[k]['id']) for k in ('before', 'after')))
        return ActionResult('completed', refs, data)
    register(ActionSpec('delivery.compare', Compare, VIEW, handle, resolve,
        audit_fields=('before_delivery_id', 'after_delivery_id')))
