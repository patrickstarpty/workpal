import hashlib
import json
from dataclasses import asdict
from workpal.contracts import DomainError, ActionResult, ObjectRef
from workpal.identity.service import require_member
from workpal.access.service import authorize, derive_scope
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from .schemas import form_schema, check_schema, clean, validate, finite_json
from .models import IdempotencyResult
from . import confirmations
from django.utils import timezone
from workpal.audit.service import record
_specs={}
_result_states = frozenset(('completed', 'accepted', 'waiting_input',
                            'waiting_confirmation', 'waiting_user_auth', 'failed', 'unknown'))


def _scope_refs(refs):
    """Retain the original sources even when a business binding later changes."""
    refs = set(refs)
    if refs:
        refs.update(derive_scope(refs).source_refs)
    return [asdict(ref) for ref in sorted(refs, key=lambda ref: (ref.kind, ref.id))]

def register(spec):
    if spec.action_id in _specs: raise ValueError('Duplicate action')
    if not spec.action_id or len(spec.action_id)>160 or spec.capability not in ('read','write','publish'): raise ValueError('Invalid action')
    if spec.confirmation_required and not spec.mutating: raise ValueError('Confirmation requires a mutating action')
    form_schema(spec.form_class); check_schema(spec.output_schema)
    _specs[spec.action_id]=spec

def catalog(actor):
    member=require_member(actor,actor.workspace_id)
    return [dict(action_id=s.action_id,schema=form_schema(s.form_class),output_schema=s.output_schema,capability=s.capability,allowed_roles=list(s.allowed_roles),authorization='current membership and source grants',mutating=s.mutating,idempotency_required=s.mutating,confirmation_required=s.confirmation_required,revision_required=s.revision_required,compensation=s.compensation) for s in _specs.values() if member.role in s.allowed_roles]

def execute(actor,request):
    spec=_specs.get(request.action_id)
    if spec is None: raise DomainError('unknown_action','Unknown action.',status=404)
    def run():
        member=require_member(actor,actor.workspace_id)
        if member.role not in spec.allowed_roles: raise DomainError('permission_denied','Permission denied.',status=403)
        if request.confirmation_id is not None and not spec.confirmation_required:
            confirmations.reject()
        payload=clean(spec.form_class,request.payload)
        if request.expected_revision is not None and (type(request.expected_revision) is not int or not 0 <= request.expected_revision <= MAX_SQLITE_INTEGER): raise DomainError('invalid_input','Invalid revision.')
        if spec.revision_required and (type(request.expected_revision) is not int or not 1 <= request.expected_revision <= MAX_SQLITE_INTEGER): raise DomainError('invalid_input','Positive revision required.')
        input_refs = tuple(spec.resolve_refs(actor, payload))
        authorize(actor, spec.capability, input_refs)
        input_scope = _scope_refs(input_refs)
        digest=hashlib.sha256(json.dumps({'payload':request.payload,'expected_revision':request.expected_revision},sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        scope=dict(workspace_id=actor.workspace_id,user_id=actor.user_id,action_id=spec.action_id,key=request.idempotency_key)
        if spec.mutating:
            if type(request.idempotency_key) is not str or not request.idempotency_key.strip() or len(request.idempotency_key)>200: raise DomainError('invalid_input','Idempotency key required.')
            confirmation = None
            if spec.confirmation_required and request.confirmation_id is not None:
                confirmations.human(actor)
                confirmation = confirmations.check(actor, request, scope, digest, input_scope)
            saved=IdempotencyResult.objects.filter(**scope).first()
            if saved:
                if spec.confirmation_required:
                    confirmations.human(actor)
                if saved.request_hash!=digest: raise DomainError('idempotency_conflict','Key already used.',status=409)
                data=saved.result
                refs=[ObjectRef(**r) for r in data['object_refs']]
                if spec.result_refs is not None:
                    cached = ActionResult(data['state'], refs, data['data'], data['error'])
                    refs = list(dict.fromkeys(refs + list(spec.result_refs(actor, cached))))
                authorize(actor, 'read', [ObjectRef(**r) for r in saved.scope_refs])
                authorize(actor,'read',refs)
                return ActionResult(data['state'],refs,data['data'],data['error'])
        if spec.confirmation_required:
            if request.confirmation_id is None:
                return confirmations.prepare(request, scope, digest, input_scope)
            if confirmation.consumed or confirmation.expires_at <= timezone.now():
                confirmations.reject()
            confirmation.consumed = True
            confirmation.save(update_fields=['consumed'])
        result=spec.handler(actor,payload,request.expected_revision)
        if not isinstance(result,ActionResult): raise ValueError('Handler must return ActionResult')
        if result.state not in _result_states: raise ValueError('Invalid action result state')
        validate(result.data,spec.output_schema); finite_json(result.error)
        if spec.result_refs is not None:
            result.object_refs[:] = list(dict.fromkeys(list(result.object_refs) + list(spec.result_refs(actor, result))))
        refs=[]
        for ref in result.object_refs:
            if not isinstance(ref,ObjectRef): raise ValueError('Invalid object reference')
            refs.append(asdict(ref))
        if result.object_refs:
            authorize(actor,'read',result.object_refs)
        # Input objects may legitimately be revoked by the handler. Their
        # pre-action scope is immutable history, not a new post-action lookup.
        history_refs = {ObjectRef(**ref) for ref in input_scope + _scope_refs(result.object_refs)}
        scope_refs = [asdict(ref) for ref in sorted(history_refs, key=lambda ref: (ref.kind, ref.id))]
        serialized=asdict(result); finite_json(serialized)
        record(actor,spec,result,payload,refs,scope_refs)
        if spec.mutating: IdempotencyResult.objects.create(**scope,request_hash=digest,result=serialized,scope_refs=scope_refs)
        return result
    return atomic_write(run)
