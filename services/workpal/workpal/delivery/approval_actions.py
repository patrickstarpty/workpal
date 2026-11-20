"""Closed read-only Registry adapter for current approval."""
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult, SubjectRef
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.workflows.contracts import DEFINITION
from .selection_actions import Current
from .actions import SUBJECT
from .artifact_actions import obj
from . import approval, service

INTEGER = dict(type='integer', minimum=0, maximum=MAX_SQLITE_INTEGER)
POSITIVE = dict(INTEGER, minimum=1)
VIEW = obj(dict(subject=SUBJECT, status=dict(type='string',enum=['approved','not_approved']),
    reason=dict(type='string',enum=['approved','no_current_delivery','review_required','changes_requested','requirements_changed','submission_changed']),
    **{key:INTEGER for key in ('current_delivery_id','current_delivery_number','review_id','review_revision')},
    current_revision=POSITIVE, requirements_revision=POSITIVE,
    completion_policy=DEFINITION['properties']['review_policy']['properties']['completion']))

def register_actions():
    from workpal.actions.registry import register
    def resolve(actor, payload):
        return service.subject_refs(actor, SubjectRef(**payload['subject']))
    def handle(actor, payload, revision):
        data, refs = approval.inspect(actor, SubjectRef(**payload['subject']))
        return ActionResult('completed', refs, data)
    register(ActionSpec('delivery.approval.read', Current, VIEW, handle, resolve,
        audit_fields=('subject',)))
