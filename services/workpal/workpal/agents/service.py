from workpal.contracts import DomainError,ObjectRef
from workpal.storage import atomic_write
from workpal.access.service import authorize,register_object
from workpal.work.service import manage
from workpal.work.issues import integer,validate_text
from workpal.identity.service import require_member
from .models import Agent
PROVIDERS=('copilot_cli','codex_cli','claude_code','gemini_cli','opencode')
def ref(pk): return ObjectRef('agent',str(pk))
def selected(actor,pk,capability='read'):
    integer(pk); require_member(actor,actor.workspace_id)
    row=Agent.objects.filter(pk=pk,workspace_id=actor.workspace_id).first()
    if row is None: raise DomainError('not_found','Agent unavailable.',status=404)
    authorize(actor,capability,[ref(pk)]); return row
def view(row):
    return dict(id=row.pk,workspace_id=row.workspace_id,name=row.name,provider_key=row.provider_key,model=row.model,revision=row.revision,created_by=row.created_by_id,created_at=row.created_at.isoformat(),capability='runtime_unavailable' if row.provider_key=='copilot_cli' else 'not_implemented')
def validate(values):
    if not values or set(values)-{'name','provider_key','model'}: raise DomainError('invalid_input','Invalid agent fields.')
    for k,v in values.items(): validate_text(v,200,k!='model')
    if 'provider_key' in values and values['provider_key'] not in PROVIDERS: raise DomainError('invalid_input','Unknown provider.')
def create(actor,name,provider_key='copilot_cli',model=''):
    def write():
        manage(actor); values=dict(name=name,provider_key=provider_key,model=model); validate(values)
        row=Agent.objects.create(workspace_id=actor.workspace_id,created_by_id=actor.user_id,**values)
        register_object(actor.workspace_id,ref(row.pk)); return view(row)
    return atomic_write(write)
def read(actor,agent_id): return view(selected(actor,agent_id))
def update(actor,agent_id,revision,**changes):
    def write():
        manage(actor); integer(revision); validate(changes); row=selected(actor,agent_id,'write')
        if not Agent.objects.filter(pk=row.pk,revision=revision).update(**changes,revision=revision+1): raise DomainError('revision_conflict','Agent changed.',status=409)
        row.refresh_from_db(); return view(row)
    return atomic_write(write)
