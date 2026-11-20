from dataclasses import asdict
from django.db.models import Q
import hashlib,json
from copy import deepcopy
from workpal.contracts import DomainError,ObjectRef
from workpal.storage import atomic_write
from workpal.access.service import authorize,register_object,derive_scope
from workpal.identity.service import require_member
from workpal.work import issues,service as projects,resources
from workpal.agents import service as agents
from .models import Run,Intent
from .contracts import ACTIVE

def ref(pk): return ObjectRef('run',str(pk))
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def selected(actor,pk,capability='read'):
    issues.integer(pk); require_member(actor,actor.workspace_id)
    row=Run.objects.filter(pk=pk,workspace_id=actor.workspace_id).first()
    if row is None: raise DomainError('not_found','Run unavailable.',status=404)
    authorize(actor,capability,[ref(pk)])
    issues.read(actor,row.issue_id); agents.read(actor,row.agent_id)
    return row
def view(row):
    return dict(id=row.pk,subject=dict(type='issue',id=row.issue_id),agent_id=row.agent_id,status=row.status,revision=row.revision,input_snapshot=deepcopy(row.input_snapshot),sha256=row.sha256,created_at=row.created_at.isoformat(),deferred_reason={'code':'runtime_unavailable'} if row.status=='deferred' else {'code':''})
def read(actor,run_id): return view(selected(actor,run_id))
def admission_refs(actor,issue,agent_id,key):
    refs=[issues.ref(issue['id']),issues.requirement_ref(issue['requirements_version_id']),agents.ref(agent_id),projects.ref(issue['project_id'])]
    from workpal.work.models import ProjectResource
    for pk in ProjectResource.objects.filter(project_id=issue['project_id']).order_by('pk').values_list('pk',flat=True):
        resources.read(actor,issue['project_id'],pk)
        refs.append(resources.ref(pk))
    # Historical Run provenance remains authoritative even after configuration changes.
    for row in Run.objects.filter(workspace_id=actor.workspace_id,issue_id=issue['id'],agent_id=agent_id).filter(Q(status__in=ACTIVE) | Q(intent__actor_id=actor.user_id,intent__key=key)).distinct():
        refs.append(ref(row.pk))
    return refs

def start(actor,subject,agent_id,key,trigger='manual'):
    def write():
        if type(subject) is not dict or set(subject)!={'type','id'} or subject['type']!='issue': raise DomainError('invalid_input','Unsupported subject.')
        issues.integer(subject['id']); issues.integer(agent_id); issues.validate_text(key,200,True)
        if trigger!='manual': raise DomainError('capability_unavailable','Node admission requires a complete instance/node/attempt contract.',status=409)
        issue=issues.read(actor,subject['id']); agent=agents.read(actor,agent_id)
        refs=admission_refs(actor,issue,agent_id,key)
        authorize(actor,'write',refs)
        d=digest(dict(subject=subject,agent_id=agent_id,trigger=trigger))
        intent=Intent.objects.filter(workspace_id=actor.workspace_id,actor_id=actor.user_id,key=key).first()
        if intent:
            if intent.digest!=d: raise DomainError('idempotency_conflict','Key already used.',status=409)
            selected(actor,intent.run_id,'write'); return read(actor,intent.run_id)
        if agent['provider_key']!='copilot_cli': raise DomainError('capability_unavailable','Provider is extension-only/not_implemented.',status=409)
        row=Run.objects.filter(workspace_id=actor.workspace_id,issue_id=issue['id'],agent_id=agent_id,status__in=ACTIVE).first()
        if row: selected(actor,row.pk,'write')
        else:
            project=projects.read(actor,issue['project_id'])
            # Enumerate every configured resource, including inaccessible ones: never silently omit provenance.
            from workpal.work.models import ProjectResource
            saved=[]
            for pk in ProjectResource.objects.filter(project_id=project['id']).order_by('pk').values_list('pk',flat=True):
                saved.append(resources.read(actor,project['id'],pk)); refs.append(resources.ref(pk))
            authorize(actor,'write',refs)
            snapshot=dict(issue=issue,requirements=issues.read_requirements(actor,issue['id'],issue['requirements_revision']),project=project,resources=saved,workflow=issue['workflow_snapshot'],agent=agent,source_refs=[asdict(r) for r in sorted(derive_scope(refs).source_refs,key=lambda r:(r.kind,r.id))])
            row=Run.objects.create(workspace_id=actor.workspace_id,created_by_id=actor.user_id,issue_id=issue['id'],requirements_id=issue['requirements_version_id'],project_id=project['id'],agent_id=agent_id,input_snapshot=snapshot,sha256=digest(snapshot))
            register_object(actor.workspace_id,ref(row.pk),refs)
        Intent.objects.create(workspace_id=actor.workspace_id,actor_id=actor.user_id,key=key,digest=d,run=row)
        return read(actor,row.pk)
    return atomic_write(write)
def control(actor,run_id,operation,revision):
    def write():
        issues.integer(revision); row=selected(actor,run_id,'write')
        if operation!='cancel': raise DomainError('capability_unavailable','Operation unavailable.',status=409)
        if row.revision!=revision: raise DomainError('revision_conflict','Run changed.',status=409)
        status='cancelled' if row.status in ('deferred','queued') else ('cancel_requested' if row.status in ACTIVE else row.status)
        if not Run.objects.filter(pk=row.pk,revision=revision).update(status=status,revision=revision+1): raise DomainError('revision_conflict','Run changed.',status=409)
        return read(actor,row.pk)
    return atomic_write(write)
