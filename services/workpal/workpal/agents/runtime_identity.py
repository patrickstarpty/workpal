"""One-time device pairing; secrets are never persisted or replayed."""
from dataclasses import dataclass, asdict
from datetime import timedelta
import hashlib
import re
import secrets
from types import SimpleNamespace
from django.utils import timezone
from workpal.contracts import Actor, DomainError, ObjectRef
from workpal.storage import atomic_write
from workpal.identity.service import require_member
from workpal.access.service import authorize, register_object, derive_scope
from workpal.audit import service as audit
from .models import Runtime, RuntimePairing

_clock = timezone.now

@dataclass(frozen=True)
class RuntimeIdentity:
    runtime_id: int
    workspace_id: int

def _fail(code, status=400):
    raise DomainError(code, 'Runtime operation unavailable.', status=status)

def _integer(value):
    if type(value) is not int or not 1 <= value <= 2**63-1:
        _fail('invalid_input')

def _manage(actor, human=False):
    if require_member(actor, actor.workspace_id).role not in ('owner', 'admin') or (human and actor.executor_id is not None):
        _fail('permission_denied', 403)

def _hash(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()

def _secret(value, prefix):
    if type(value) is not str or re.fullmatch(prefix + r'[0-9a-f]{64}', value) is None:
        _fail('authentication_required', 401)
    return _hash(value)

def _record(actor, action, payload):
    refs = [ObjectRef('runtime_pairing', str(payload['pairing_id']))]
    if 'runtime_id' in payload:
        refs.append(ObjectRef('runtime', str(payload['runtime_id'])))
    scope = sorted(set(refs) | derive_scope(refs).source_refs, key=lambda ref: (ref.kind, ref.id))
    audit.record(actor, SimpleNamespace(action_id=action, audit_fields=tuple(payload), mutating=True),
                 SimpleNamespace(state='completed'), payload,
                 [asdict(ref) for ref in refs], [asdict(ref) for ref in scope])

def _selected(actor, pk, model, kind, capability='read'):
    _integer(pk)
    _manage(actor)
    row = model.objects.filter(pk=pk, workspace_id=actor.workspace_id).first()
    if row is None:
        _fail('not_found', 404)
    authorize(actor, capability, [ObjectRef(kind, str(pk))])
    return row

def _view(row):
    return dict(id=row.pk, workspace_id=row.workspace_id, name=row.name,
                revision=row.revision, revoked=row.revoked_at is not None)

def issue_pairing(actor, name):
    def write():
        _manage(actor, True)
        if type(name) is not str or not name.strip() or len(name) > 200:
            _fail('invalid_input')
        try:
            name.encode('utf-8')
        except UnicodeError:
            _fail('invalid_input')
        secret = 'wp_pair_' + secrets.token_hex(32)
        row = RuntimePairing.objects.create(workspace_id=actor.workspace_id, created_by_id=actor.user_id,
            name=name, secret_hash=_hash(secret), expires_at=_clock()+timedelta(seconds=600))
        register_object(actor.workspace_id, ObjectRef('runtime_pairing', str(row.pk)))
        _record(actor, 'runtime.pairing.issue', {'pairing_id': row.pk})
        return dict(pairing_id=row.pk, secret=secret, expires_at=row.expires_at.isoformat())
    return atomic_write(write)

def read_pairing(actor, pairing_id):
    row = _selected(actor, pairing_id, RuntimePairing, 'runtime_pairing')
    return dict(pairing_id=row.pk, name=row.name, expires_at=row.expires_at.isoformat(),
                consumed=row.consumed_at is not None, runtime_id=row.runtime_id or 0)

def consume_pairing(secret):
    digest = _secret(secret, 'wp_pair_')
    def write():
        row = RuntimePairing.objects.filter(secret_hash=digest).first()
        if row is None:
            _fail('authentication_required', 401)
        now = _clock()
        if row.consumed_at is not None or row.expires_at <= now:
            _fail('pairing_unavailable', 409)
        actor = Actor(row.created_by_id, row.workspace_id)
        try:
            _manage(actor)
        except DomainError as error:
            if error.status in (403, 404):
                _fail('permission_denied', 403)
            raise
        if not RuntimePairing.objects.filter(pk=row.pk, consumed_at=None, expires_at__gt=now, revision=row.revision).update(consumed_at=now, revision=row.revision+1):
            _fail('pairing_unavailable', 409)
        token = 'wp_runtime_' + secrets.token_hex(32)
        runtime = Runtime.objects.create(workspace_id=row.workspace_id, created_by_id=row.created_by_id,
                                         name=row.name, credential_hash=_hash(token))
        register_object(row.workspace_id, ObjectRef('runtime', str(runtime.pk)))
        RuntimePairing.objects.filter(pk=row.pk).update(runtime=runtime)
        _record(actor, 'runtime.pairing.consume', {'pairing_id': row.pk, 'runtime_id': runtime.pk})
        return dict(runtime_id=runtime.pk, runtime_token=token)
    return atomic_write(write)

def authenticate_runtime(secret):
    row = Runtime.objects.filter(credential_hash=_secret(secret, 'wp_runtime_'), revoked_at=None).first()
    if row is None:
        _fail('authentication_required', 401)
    return RuntimeIdentity(row.pk, row.workspace_id)

def read_runtime(actor, runtime_id):
    return _view(_selected(actor, runtime_id, Runtime, 'runtime'))

def revoke(actor, runtime_id, revision):
    def write():
        _manage(actor, True)
        _integer(revision)
        row = _selected(actor, runtime_id, Runtime, 'runtime', 'write')
        if row.revision != revision:
            _fail('revision_conflict', 409)
        if row.revoked_at is None:
            if revision >= 2**31-1:
                _fail('invalid_input')
            if not Runtime.objects.filter(pk=row.pk, revision=revision).update(revoked_at=_clock(), revision=revision+1):
                _fail('revision_conflict', 409)
            row.refresh_from_db()
        return _view(row)
    return atomic_write(write)


def _binding_context(actor, agent_id, runtime_id=None):
    from .models import Agent, RuntimeBinding
    _manage(actor, True)
    agent = _selected(actor, agent_id, Agent, 'agent', 'write')
    binding = RuntimeBinding.objects.filter(agent=agent, workspace_id=actor.workspace_id).first()
    refs = [ObjectRef('agent', str(agent.pk))]
    if binding is not None:
        _selected(actor, binding.runtime_id, Runtime, 'runtime', 'write')
        refs.append(ObjectRef('runtime', str(binding.runtime_id)))
    target = None
    if runtime_id is not None:
        target = _selected(actor, runtime_id, Runtime, 'runtime', 'write')
        refs.append(ObjectRef('runtime', str(target.pk)))
    return agent, binding, target, refs


def _change_binding(actor, agent_id, runtime_id, revision):
    from .models import Agent, RuntimeBinding
    def write():
        _integer(revision)
        agent, binding, target, _ = _binding_context(actor, agent_id, runtime_id)
        if agent.revision != revision:
            _fail('revision_conflict', 409)
        if target is not None and target.revoked_at is not None:
            _fail('capability_unavailable', 409)
        if target is None and (binding is None or not binding.enabled):
            _fail('capability_unavailable', 409)
        if revision >= 2**31-1 or (binding is not None and binding.revision >= 2**31-1):
            _fail('invalid_input')
        if not Agent.objects.filter(pk=agent.pk, revision=revision).update(revision=revision+1):
            _fail('revision_conflict', 409)
        if binding is None:
            binding = RuntimeBinding.objects.create(workspace_id=actor.workspace_id, agent=agent, runtime=target)
        else:
            old = binding.revision
            if target is not None:
                binding.runtime = target
            binding.enabled = target is not None
            binding.revision += 1
            if not RuntimeBinding.objects.filter(pk=binding.pk, revision=old).update(
                    runtime_id=binding.runtime_id, enabled=binding.enabled, revision=binding.revision):
                _fail('revision_conflict', 409)
        return dict(agent_id=agent.pk, runtime_id=binding.runtime_id, revision=revision+1,
                    binding_revision=binding.revision, enabled=binding.enabled)
    return atomic_write(write)


def bind(actor, agent_id, runtime_id, revision):
    _integer(runtime_id)
    return _change_binding(actor, agent_id, runtime_id, revision)


def unbind(actor, agent_id, revision):
    return _change_binding(actor, agent_id, None, revision)
