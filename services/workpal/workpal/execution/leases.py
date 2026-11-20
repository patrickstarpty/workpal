"""Read-only task identity. Future operations must recheck current authorization."""
import hashlib
import re
from datetime import datetime, timedelta
from django.utils import timezone
from workpal.contracts import DomainError
from .models import TaskToken
from .protocol import TaskIdentity

__all__ = ['authenticate_task']
_clock = timezone.now

def authenticate_task(secret: str) -> TaskIdentity:
    if type(secret) is not str or re.fullmatch(r'wp_task_[0-9a-f]{64}', secret) is None:
        raise DomainError('authentication_required', 'Task identity unavailable.', status=401)
    return _authenticate_at(secret, _clock())

def _authenticate_at(secret, now):
    if type(secret) is not str or re.fullmatch(r'wp_task_[0-9a-f]{64}', secret) is None:
        raise DomainError('authentication_required', 'Task identity unavailable.', status=401)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise DomainError('invalid_input', 'Invalid clock.', status=400)
    token = TaskToken.objects.select_related('runtime').filter(
        secret_hash=hashlib.sha256(secret.encode('ascii')).hexdigest(),
        revoked_at=None, runtime__revoked_at=None, expires_at__gt=now).first()
    if token is None:
        raise DomainError('authentication_required', 'Task identity unavailable.', status=401)
    return TaskIdentity(token.runtime_id, token.runtime.workspace_id, token.run_id, token.epoch, token.pk)

from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
import secrets
from workpal.contracts import Actor, ObjectRef, ActionResult
from workpal.storage import atomic_write
from workpal.access.service import authorize, derive_scope
from workpal.identity.service import require_member
from workpal.agents.runtime_identity import authenticate_runtime
from workpal.agents.models import RuntimeBinding
from workpal.work import issues, service as projects, resources
from workpal.work.models import ProjectResource
from workpal.agents import service as agents
from workpal.audit import service as audit
from .models import Run, RuntimeClaimScan
from .protocol import CapabilityReport, ClaimResult, Lease
from . import service as runs

__all__.append('claim')

def _verify_capabilities(*, runtime_id, workspace_id, agent_id, provider_key, now):
    return False

def _capable(identity, agent_id, now):
    result = _verify_capabilities(runtime_id=identity.runtime_id, workspace_id=identity.workspace_id,
                                  agent_id=agent_id, provider_key='copilot_cli', now=now)
    if type(result) is not bool:
        raise DomainError('invalid_input', 'Invalid capability verification.')
    return result

def _claim_refs(row):
    actor = Actor(row.created_by_id, row.workspace_id)
    require_member(actor, row.workspace_id)
    refs = [runs.ref(row.pk)]
    saved = row.input_snapshot['source_refs']
    for value in saved:
        if type(value) is not dict or set(value) != {'kind', 'id'} or any(type(value[k]) is not str or not value[k] for k in value):
            raise DomainError('storage_unavailable', 'Invalid provenance.', status=503)
        refs.append(ObjectRef(**value))
    authorize(actor, 'write', refs)
    issue = issues.read(actor, row.issue_id)
    requirement = issues.read_requirements(actor, row.issue_id, row.input_snapshot['requirements']['number'])
    if requirement['id'] != row.requirements_id:
        raise DomainError('not_found', 'Requirements unavailable.', status=404)
    agent = agents.read(actor, row.agent_id)
    projects.read(actor, issue['project_id'])
    refs += [issues.ref(row.issue_id), issues.requirement_ref(row.requirements_id), agents.ref(row.agent_id), projects.ref(issue['project_id'])]
    for pk in ProjectResource.objects.filter(project_id=issue['project_id']).order_by('pk').values_list('pk', flat=True):
        resources.read(actor, issue['project_id'], pk)
        refs.append(resources.ref(pk))
    authorize(actor, 'write', refs)
    scope = derive_scope(refs)
    if scope.workspace_id != row.workspace_id:
        raise DomainError('not_found', 'Scope unavailable.', status=404)
    return actor, agent, [asdict(r) for r in sorted(set(refs) | scope.source_refs, key=lambda r: (r.kind, r.id))]

def claim(runtime_secret: str, capabilities: CapabilityReport) -> ClaimResult:
    providers = {'copilot_cli', 'codex_cli', 'claude_code', 'gemini_cli', 'opencode'}
    if (type(capabilities) is not CapabilityReport or type(capabilities.provider_key) is not str
        or capabilities.provider_key not in providers or type(capabilities.version) is not int or capabilities.version != 1
        or any(type(getattr(capabilities, k)) is not bool for k in ('installed', 'authenticated', 'execution_ready'))):
        raise DomainError('invalid_input', 'Invalid capability report.')
    def write():
        identity = authenticate_runtime(runtime_secret)
        now = _clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise DomainError('invalid_input', 'Invalid clock.')
        try:
            expiry, token_expiry = now + timedelta(seconds=45), now + timedelta(seconds=60)
        except OverflowError:
            raise DomainError('invalid_input', 'Invalid clock.')
        if capabilities.provider_key != 'copilot_cli' or not all((capabilities.installed, capabilities.authenticated, capabilities.execution_ready)) or not _capable(identity, 0, now):
            raise DomainError('capability_unavailable', 'Capability unavailable.', status=409)
        scan, _ = RuntimeClaimScan.objects.get_or_create(runtime_id=identity.runtime_id)
        if scan.revision >= 2**63-1:
            raise DomainError('invalid_input', 'Revision overflow.')
        candidates = Run.objects.filter(workspace_id=identity.workspace_id, status='deferred', lease_epoch=0, lease_owner=None,
            agent_id__in=RuntimeBinding.objects.filter(workspace_id=identity.workspace_id, runtime_id=identity.runtime_id, enabled=True).values('agent_id')).order_by('pk')
        page = list(candidates.filter(pk__gt=scan.last_pk)[:32])
        if not page:
            page = list(candidates[:32])
        position = 0
        result = ClaimResult(None)
        for row in page:
            position = row.pk
            binding = RuntimeBinding.objects.get(agent_id=row.agent_id)
            try:
                actor, agent, scope = _claim_refs(row)
            except DomainError as error:
                if (error.code, error.status) in {('permission_denied',403), ('not_found',404), ('authentication_required',401)}:
                    continue
                raise
            if agent['provider_key'] != 'copilot_cli' or row.input_snapshot['agent']['provider_key'] != 'copilot_cli' or not _capable(identity, row.agent_id, now):
                continue
            if row.revision >= 2**31-1 or row.lease_epoch >= 2**63-1:
                raise DomainError('invalid_input', 'Revision overflow.')
            if not RuntimeBinding.objects.filter(pk=binding.pk, revision=binding.revision, enabled=True, runtime_id=identity.runtime_id, workspace_id=identity.workspace_id).update(revision=binding.revision):
                from django.db import OperationalError
                raise OperationalError('locked binding')
            if not Run.objects.filter(pk=row.pk, revision=row.revision, status='deferred', lease_epoch=0, lease_owner=None).update(status='dispatched',revision=row.revision+1,lease_epoch=1,lease_owner_id=identity.runtime_id,lease_expires_at=expiry):
                from django.db import OperationalError
                raise OperationalError('locked run')
            secret = 'wp_task_' + secrets.token_hex(32)
            TaskToken.objects.filter(run=row, revoked_at=None).update(revoked_at=now)
            TaskToken.objects.create(run=row,runtime_id=identity.runtime_id,epoch=1,secret_hash=hashlib.sha256(secret.encode('ascii')).hexdigest(),expires_at=token_expiry,scope_refs=scope)
            payload = dict(run_id=row.pk,runtime_id=identity.runtime_id,epoch=1,status='dispatched',reason='claimed')
            audit.record(actor,SimpleNamespace(action_id='runtime.claim',audit_fields=tuple(payload),mutating=True),ActionResult('completed',[],{}),payload,[asdict(runs.ref(row.pk))],scope)
            result = ClaimResult(Lease(row.pk,1,expiry,deepcopy(row.input_snapshot),secret))
            break
        if not RuntimeClaimScan.objects.filter(runtime_id=identity.runtime_id,revision=scan.revision).update(last_pk=position,revision=scan.revision+1):
            from django.db import OperationalError
            raise OperationalError('locked scan')
        return result
    return atomic_write(write)

from .protocol import Renewal, Renewed, StopOnly, Denied
from workpal.access.models import RegisteredObject, SourceLink
__all__.append('renew')


def _stop_scope(row, token):
    if type(token.scope_refs) is not list or not token.scope_refs:
        raise DomainError('storage_unavailable', 'Invalid provenance.', status=503)
    pending = list(token.scope_refs) + [asdict(runs.ref(row.pk))]
    seen = set()
    while pending:
        value = pending.pop()
        if (type(value) is not dict or set(value) != {'kind', 'id'}
            or any(type(value[k]) is not str or not value[k] for k in value)):
            raise DomainError('storage_unavailable', 'Invalid provenance.', status=503)
        key = (value['kind'], value['id'])
        if key in seen:
            continue
        obj = RegisteredObject.objects.filter(kind=key[0], object_id=key[1]).first()
        if obj is None or obj.workspace_id != row.workspace_id:
            raise DomainError('storage_unavailable', 'Invalid provenance.', status=503)
        seen.add(key)
        pending.extend({'kind': source.kind, 'id': source.object_id}
                       for source in RegisteredObject.objects.filter(
                           pk__in=SourceLink.objects.filter(derived=obj).values('source_id')))
    return [dict(kind=k, id=i) for k, i in sorted(seen)]


def renew(task_secret: str, *, run_id: int, epoch: int) -> Renewed | StopOnly | Denied:
    def write():
        now = _clock()
        try:
            identity = _authenticate_at(task_secret, now)
        except DomainError as error:
            if error.status == 401:
                return Denied(error.code, error.status)
            raise
        if any(type(v) is not int or v <= 0 or v > 2**63-1 for v in (run_id, epoch)):
            raise DomainError('invalid_input', 'Invalid lease identifier.')
        row = Run.objects.get(pk=identity.run_id)
        if row.pk != run_id:
            return Denied('not_found', 404)
        if epoch != identity.epoch or epoch != row.lease_epoch:
            return Denied('stale_epoch', 409)
        if row.status in {'completed', 'failed', 'cancelled', 'awaiting_input'}:
            return Denied('lease_conflict', 409)
        token = TaskToken.objects.get(pk=identity.token_id)
        reason = None
        status = row.status
        binding = None
        if status in {'cancel_requested', 'recovery_required'}:
            reason = 'stop_observed'
        elif row.lease_expires_at is None or now >= row.lease_expires_at:
            reason, status = 'lease_expired', 'recovery_required'
        elif status not in {'dispatched', 'waiting_local_directory', 'running'}:
            return Denied('lease_conflict', 409)
        else:
            try:
                actor, agent, scope = _claim_refs(row)
            except DomainError as error:
                if (error.code, error.status) not in {('permission_denied',403), ('not_found',404), ('authentication_required',401)}:
                    raise
                reason, status = 'authorization_revoked', 'cancel_requested'
            if reason is None:
                binding = RuntimeBinding.objects.filter(agent_id=row.agent_id, workspace_id=row.workspace_id,
                    runtime_id=identity.runtime_id, enabled=True).first()
                if (binding is None or row.lease_owner_id != identity.runtime_id
                    or agent['provider_key'] != 'copilot_cli'
                    or row.input_snapshot['agent']['provider_key'] != 'copilot_cli'
                    or not _capable(identity, row.agent_id, now)):
                    reason, status = 'authorization_revoked', 'cancel_requested'
        if row.revision >= 2**31-1:
            raise DomainError('invalid_input', 'Revision overflow.')
        if reason:
            scope = _stop_scope(row, token)
        else:
            scope = [dict(kind=k,id=i) for k,i in sorted({(v['kind'],v['id']) for v in scope + _stop_scope(row, token)})]
            try:
                expiry, token_expiry = now + timedelta(seconds=45), now + timedelta(seconds=60)
            except OverflowError:
                raise DomainError('invalid_input', 'Invalid clock.')
            if not RuntimeBinding.objects.filter(pk=binding.pk, revision=binding.revision, enabled=True,
                    runtime_id=identity.runtime_id).update(revision=binding.revision):
                from django.db import OperationalError
                raise OperationalError('locked binding')
        changes = dict(status=status, revision=row.revision+1)
        if reason is None:
            changes['lease_expires_at'] = expiry
        if not Run.objects.filter(pk=row.pk, revision=row.revision, status=row.status,
                lease_epoch=epoch, lease_owner_id=row.lease_owner_id).update(**changes):
            from django.db import OperationalError
            raise OperationalError('locked run')
        if not TaskToken.objects.filter(pk=token.pk, revoked_at=None, epoch=epoch,
                runtime_id=identity.runtime_id, expires_at__gt=now).update(revoked_at=now):
            from django.db import OperationalError
            raise OperationalError('locked token')
        if reason:
            TaskToken.objects.filter(run=row, revoked_at=None).update(revoked_at=now)
        else:
            secret = 'wp_task_' + secrets.token_hex(32)
            TaskToken.objects.create(run=row, runtime_id=identity.runtime_id, epoch=epoch,
                secret_hash=hashlib.sha256(secret.encode('ascii')).hexdigest(), expires_at=token_expiry, scope_refs=scope)
        payload = dict(run_id=row.pk,runtime_id=identity.runtime_id,epoch=epoch,status=status,reason=reason or 'renewed')
        audit.record(Actor(row.created_by_id,row.workspace_id),
            SimpleNamespace(action_id='runtime.renew',audit_fields=tuple(payload),mutating=True),
            ActionResult('completed',[],{}),payload,[asdict(runs.ref(row.pk))],scope)
        return StopOnly(row.pk,epoch,reason) if reason else Renewed(Renewal(row.pk,epoch,expiry,secret))
    return atomic_write(write)
