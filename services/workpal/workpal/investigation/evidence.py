"""Restricted policy management and immutable, normalized evidence snapshots."""
from copy import deepcopy
from workpal.contracts import DomainError
from workpal.access.service import authorize
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from . import environments as env, sources
from .models import Source, EvidencePolicyVersion
from .normalization import normalize_upload


def selected(actor, source_id):
    env.integer(source_id)
    env.projects.manage(actor)
    if actor.executor_id is not None:
        raise DomainError('permission_denied', 'Human policy management required.', status=403)
    source=Source.objects.filter(pk=source_id,environment__workspace_id=actor.workspace_id).first()
    if source is None:
        raise DomainError('not_found','Source unavailable.',status=404)
    env.selected(actor,source.environment_id,'write')
    authorize(actor,'read',[sources.source_ref(source.pk)])
    authorize(actor,'publish',[sources.source_ref(source.pk)])
    if source.adapter_type!='upload':
        raise DomainError('invalid_input','Upload source required.')
    return source


def configure_policy(actor, source_id, policy, expected_revision):
    env.integer(source_id)
    env.integer(expected_revision,maximum=MAX_SQLITE_INTEGER-1)
    def write():
        source=selected(actor,source_id)
        copied=deepcopy(policy)
        digest=normalize_upload(b'',format='jsonl',policy=copied)['policy_sha256']
        if not Source.objects.filter(pk=source.pk,policy_revision=expected_revision).update(policy_revision=expected_revision+1):
            raise DomainError('revision_conflict','Policy changed.',status=409)
        version=EvidencePolicyVersion.objects.create(source=source,revision=expected_revision+1,policy=copied,policy_sha256=digest,creator_id=actor.user_id)
        Source.objects.filter(pk=source.pk).update(current_policy=version)
        return dict(source_id=source.pk,revision=version.revision,policy_sha256=digest)
    return atomic_write(write)


def read_policy(actor, source_id):
    source=selected(actor,source_id)
    result=dict(source_id=source.pk,revision=source.policy_revision,configured=source.current_policy_id is not None,policy_sha256='')
    if source.current_policy_id is not None:
        result.update(policy=deepcopy(source.current_policy.policy),policy_sha256=source.current_policy.policy_sha256)
    return result


from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from workpal.contracts import ObjectRef, ActionRequest
from workpal.identity.service import require_member
from workpal.access.service import register_object
from .models import Investigation, EvidenceSnapshot
from . import service

@dataclass(frozen=True)
class _PreparedUpload:
    actor: object
    key: str
    payload: dict
    normalized: dict
    policy_id: int
    timezone: str

_prepared = ContextVar('evidence_prepared', default=None)
def ref(pk): return ObjectRef('evidence',str(pk))

def _authorized(actor, investigation_id, source_id, write=False):
    require_member(actor,actor.workspace_id)
    env.integer(investigation_id); env.integer(source_id)
    investigation=Investigation.objects.filter(pk=investigation_id,workspace_id=actor.workspace_id).first()
    source=Source.objects.filter(pk=source_id,environment__workspace_id=actor.workspace_id).first()
    if investigation is None or source is None:
        raise DomainError('not_found','Evidence target unavailable.',status=404)
    env.selected(actor,investigation.environment_id,'write' if write else 'read')
    refs=[service.ref(investigation.pk),sources.source_ref(source.pk),service.service_ref(investigation.service_id)]
    authorize(actor,'read',refs)
    if source.adapter_type!='upload' or source.environment_id!=investigation.environment_id or not source.allowed_services.filter(pk=investigation.service_id).exists() or investigation.service.environment_id!=investigation.environment_id or investigation.project_id!=investigation.environment.project_id:
        raise DomainError('permission_denied','Evidence source unavailable.',status=403)
    return investigation,source,refs

def _metadata(row):
    names=['id','investigation_id','environment_id','service_id','source_id','actor_id','timezone','range_start','range_end','event_time','deployment_id','commit_sha','original_location','origin','coverage','format','status','raw_sha256','content_sha256','policy_sha256','raw_bytes','content_bytes','total_records','included_records','included_line_numbers','truncated','redaction_count','omitted_fields']
    return dict({name:getattr(row,name) for name in names},created_at=row.created_at.isoformat(),policy_revision=row.policy_version.revision)

def _digest(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def submit_upload(actor, investigation_id, source_id, content, *, format, timezone=None, range_start=None, range_end=None, key):
    investigation,source,_=_authorized(actor,investigation_id,source_id,True)
    env.text(key,200)
    if type(content) is not bytes: raise DomainError('invalid_input','Bytes required.')
    if timezone is not None: env.valid_timezone(timezone)
    try:
        if (range_start is None)!=(range_end is None): raise ValueError
        if range_start is not None:
            if any(type(x) is not str or len(x)>64 for x in (range_start,range_end)): raise ValueError
            start,end=map(datetime.fromisoformat,(range_start,range_end))
            if start.utcoffset() is None or end.utcoffset() is None or start>=end: raise ValueError
    except (ValueError,TypeError): raise DomainError('invalid_input','Invalid range.') from None
    payload=dict(investigation_id=investigation_id,source_id=source_id,format=format,timezone=timezone,range_start=range_start,range_end=range_end,raw_sha256=hashlib.sha256(content).hexdigest(),raw_bytes=len(content))
    old=EvidenceSnapshot.objects.filter(workspace_id=actor.workspace_id,actor_id=actor.user_id,key=key).first()
    if old and old.request_hash!=_digest(payload): raise DomainError('idempotency_conflict','Key already used.',status=409)
    policy=old.policy_version if old else source.current_policy
    if policy is None: raise DomainError('policy_required','Policy required.',status=403)
    normalized=normalize_upload(content,format=format,policy=policy.policy)
    prepared=_PreparedUpload(actor,key,payload,normalized,policy.pk,old.timezone if old else timezone or investigation.environment.timezone)
    token=_prepared.set(prepared)
    try:
        from workpal.actions.registry import execute
        return execute(actor,ActionRequest('evidence.upload',_wire(payload),None,key)).data
    finally: _prepared.reset(token)

def _wire(payload):
    return {k:('' if v is None else v) for k,v in payload.items()}

def _resolve_upload(actor,payload):
    prepared=_prepared.get()
    if prepared is None or prepared.actor!=actor or _wire(prepared.payload)!=payload:
        raise DomainError('permission_denied','Internal upload capability required.',status=403)
    return _authorized(actor,payload['investigation_id'],payload['source_id'],True)[2]

def _store(actor,payload):
    prepared=_prepared.get()
    payload=prepared.payload
    investigation,source,refs=_authorized(actor,payload['investigation_id'],payload['source_id'],True)
    old=EvidenceSnapshot.objects.filter(workspace_id=actor.workspace_id,actor_id=actor.user_id,key=prepared.key).first()
    if old: return _metadata(old)
    if source.current_policy_id!=prepared.policy_id: raise DomainError('policy_changed','Policy changed.',status=409)
    row=EvidenceSnapshot.objects.create(workspace_id=actor.workspace_id,project_id=investigation.project_id,environment_id=investigation.environment_id,service_id=investigation.service_id,source=source,investigation=investigation,actor_id=actor.user_id,policy_version_id=prepared.policy_id,key=prepared.key,request_hash=_digest(payload),timezone=prepared.timezone,range_start=payload['range_start'],range_end=payload['range_end'],**prepared.normalized)
    register_object(actor.workspace_id,ref(row.pk),refs)
    return _metadata(row)

def _read(actor,evidence_id):
    env.integer(evidence_id)
    row=EvidenceSnapshot.objects.filter(pk=evidence_id,workspace_id=actor.workspace_id).first()
    if row is None: raise DomainError('not_found','Evidence unavailable.',status=404)
    _authorized(actor,row.investigation_id,row.source_id)
    authorize(actor,'read',[ref(row.pk)])
    return row

def read_evidence(actor,evidence_id):
    from workpal.actions.registry import execute
    return execute(actor,ActionRequest('evidence.read',dict(evidence_id=evidence_id),None,None)).data


def _list(actor, investigation_id, cursor=0, limit=50):
    require_member(actor, actor.workspace_id)
    env.integer(investigation_id)
    env.integer(cursor, minimum=0)
    env.integer(limit, maximum=200)
    investigation = Investigation.objects.filter(pk=investigation_id, workspace_id=actor.workspace_id).first()
    if investigation is None:
        raise DomainError('not_found', 'Investigation unavailable.', status=404)
    authorize(actor, 'read', [service.ref(investigation.pk)])
    rows = EvidenceSnapshot.objects.filter(investigation=investigation, workspace_id=actor.workspace_id, pk__gt=cursor).select_related('policy_version').defer('content', 'policy_version__policy').order_by('pk')
    visible = []
    for row in rows.iterator():
        try:
            _authorized(actor, investigation.pk, row.source_id)
            authorize(actor, 'read', [ref(row.pk)])
        except DomainError as error:
            if error.status == 403:
                continue
            raise
        visible.append(_metadata(row))
        if len(visible) > limit:
            break
    return dict(items=visible[:limit], next_cursor=visible[limit-1]['id'] if len(visible)>limit else 0)


def list_evidence(actor, investigation_id, cursor=0, limit=50):
    env.integer(investigation_id)
    env.integer(cursor, minimum=0)
    env.integer(limit, maximum=200)
    from workpal.actions.registry import execute
    return execute(actor, ActionRequest('evidence.list', dict(investigation_id=investigation_id, cursor=cursor, limit=limit), None, None)).data


def authorize_upload(actor, investigation_id, source_id) -> None:
    """Check current upload access before transport reads untrusted bytes."""
    _authorized(actor, investigation_id, source_id, write=True)
