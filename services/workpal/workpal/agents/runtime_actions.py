"""Current management authorization is resolved before cached results."""
from django import forms
from workpal.actions.contracts import ActionSpec
from workpal.actions.registry import register
from workpal.contracts import ActionResult, ObjectRef
from workpal.work.actions import obj
from . import runtime_identity as core
from .models import Agent, Runtime, RuntimePairing

class PairingSelect(forms.Form):
    pairing_id = forms.IntegerField(min_value=1, max_value=2**63-1)

class RuntimeSelect(forms.Form):
    runtime_id = forms.IntegerField(min_value=1, max_value=2**63-1)

I = {'type':'integer'}
S = {'type':'string'}
B = {'type':'boolean'}
PAIRING = obj(dict(pairing_id=I, name=S, expires_at=S, consumed=B, runtime_id=I))
RUNTIME = obj(dict(id=I, workspace_id=I, name=S, revision=I, revoked=B))


def register_actions():
    for name in ('bind', 'unbind'):
        def resolve_binding(actor, payload):
            return core._binding_context(actor, payload['agent_id'], payload.get('runtime_id'))[3]
        def result_binding(actor, result):
            core._manage(actor, True)
            core._selected(actor, result.data['agent_id'], Agent, 'agent', 'write')
            core._selected(actor, result.data['runtime_id'], Runtime, 'runtime', 'write')
            return [ObjectRef('agent', str(result.data['agent_id'])), ObjectRef('runtime', str(result.data['runtime_id']))]
        def handle_binding(actor, payload, revision, name=name):
            data = (core.bind(actor, payload['agent_id'], payload['runtime_id'], revision)
                    if name == 'bind' else core.unbind(actor, payload['agent_id'], revision))
            return ActionResult('completed', [], data)
        register(ActionSpec('runtime.'+name, BindingTarget if name == 'bind' else BindingSelect,
            obj(dict(agent_id=I, runtime_id=I, revision=I, binding_revision=I, enabled=B)),
            handle_binding, resolve_binding, capability='write', allowed_roles=('owner','admin'),
            mutating=True, revision_required=True, audit_fields=('agent_id','runtime_id') if name == 'bind' else ('agent_id',),
            result_refs=result_binding))
    for action in ('pairing.read', 'read', 'revoke'):
        pairing = action == 'pairing.read'
        field = 'pairing_id' if pairing else 'runtime_id'
        kind = 'runtime_pairing' if pairing else 'runtime'
        def resolve(actor, payload, action=action, field=field, kind=kind):
            core._manage(actor, action == 'revoke')
            core._selected(actor, payload[field], RuntimePairing if kind == 'runtime_pairing' else Runtime,
                           kind, 'write' if action == 'revoke' else 'read')
            return [ObjectRef(kind, str(payload[field]))]
        def handler(actor, payload, revision, action=action, field=field, kind=kind):
            pk = payload[field]
            data = (core.read_pairing(actor, pk) if action == 'pairing.read' else
                    core.revoke(actor, pk, revision) if action == 'revoke' else core.read_runtime(actor, pk))
            return ActionResult('completed', [ObjectRef(kind, str(pk))], data)
        register(ActionSpec('runtime.'+action, PairingSelect if pairing else RuntimeSelect,
            PAIRING if pairing else RUNTIME, handler, resolve,
            capability='write' if action == 'revoke' else 'read', allowed_roles=('owner','admin'),
            mutating=action == 'revoke', revision_required=action == 'revoke', audit_fields=(field,)))

class BindingSelect(forms.Form):
    agent_id = forms.IntegerField(min_value=1, max_value=2**63-1)

class BindingTarget(BindingSelect):
    runtime_id = forms.IntegerField(min_value=1, max_value=2**63-1)
