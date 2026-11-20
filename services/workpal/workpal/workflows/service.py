import builtins
import copy
import hashlib
import json
from django.utils import timezone
from workpal.contracts import DomainError, ObjectRef
from workpal.access.service import authorize, register_object
from workpal.identity.service import require_member
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from workpal.actions.schemas import clean
from .models import WorkflowDraft, WorkflowVersion
from .contracts import default_definition

def ref(pk, version=False):
    return ObjectRef('workflow_version' if version else 'workflow', str(pk))
def manage(actor):
    if require_member(actor, actor.workspace_id).role not in ('owner','admin'):
        raise DomainError('permission_denied','Permission denied.',status=403)
def selected(actor, pk, capability='read', version=False):
    require_member(actor, actor.workspace_id)
    row = (WorkflowVersion if version else WorkflowDraft).objects.filter(pk=pk,workspace_id=actor.workspace_id).first()
    if row is None:
        raise DomainError('not_found','Workflow unavailable.',status=404)
    authorize(actor,capability,[ref(pk,version)])
    return row
def view(row, version=False, metadata=False):
    data = dict(id=row.pk,name=row.name)
    if version:
        data.update(draft_id=row.draft_id,number=row.number,sha256=row.sha256,published_by=row.published_by_id,published_at=row.published_at.isoformat())
    else:
        data.update(revision=row.revision,version_id=row.current_version_id or 0,created_at=row.created_at.isoformat(),updated_at=row.updated_at.isoformat())
    if not metadata:
        data['definition']=copy.deepcopy(row.definition)
    return data
def create(actor, name, definition=None):
    from .actions import Create
    def write():
        manage(actor)
        data=clean(Create,dict(name=name,definition=default_definition() if definition is None else definition))
        row=WorkflowDraft.objects.create(workspace_id=actor.workspace_id,**data)
        register_object(actor.workspace_id,ref(row.pk))
        return view(row)
    return atomic_write(write)
def read(actor,draft_id):
    return view(selected(actor,draft_id))
def read_version(actor,version_id):
    return view(selected(actor,version_id,version=True),True)
def update(actor,draft_id,revision,**changes):
    from .actions import Update
    def write():
        manage(actor)
        data=clean(Update,dict(draft_id=draft_id,**changes)); data.pop('draft_id')
        row=selected(actor,draft_id,'write')
        cas(row,revision,data)
        return view(row)
    return atomic_write(write)
def cas(row,revision,changes):
    if type(revision) is not int or not 1 <= revision < MAX_SQLITE_INTEGER:
        raise DomainError('invalid_input','Invalid revision.')
    if not WorkflowDraft.objects.filter(pk=row.pk,revision=revision).update(**changes,revision=revision+1,updated_at=timezone.now()):
        raise DomainError('revision_conflict','Workflow changed.',status=409)
    row.refresh_from_db()
def publish(actor,draft_id,revision):
    def write():
        manage(actor)
        row=selected(actor,draft_id,'publish')
        cas(row,revision,{})
        number=(WorkflowVersion.objects.filter(draft=row).count()+1)
        digest=hashlib.sha256(json.dumps(dict(name=row.name,definition=row.definition),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        version=WorkflowVersion.objects.create(workspace_id=actor.workspace_id,draft=row,number=number,name=row.name,definition=copy.deepcopy(row.definition),sha256=digest,published_by_id=actor.user_id)
        register_object(actor.workspace_id,ref(version.pk,True),[ref(row.pk)])
        row.current_version=version
        row.save(update_fields=['current_version'])
        return view(version,True)
    return atomic_write(write)
def list(actor,cursor=0,limit=50):
    require_member(actor,actor.workspace_id)
    if type(cursor) is not int or not 0<=cursor<=MAX_SQLITE_INTEGER or type(limit) is not int or not 1<=limit<=200:
        raise DomainError('invalid_input','Invalid pagination.')
    visible=[]
    for row in WorkflowDraft.objects.filter(workspace_id=actor.workspace_id,pk__gt=cursor).order_by('pk').iterator():
        try:
            authorize(actor,'read',[ref(row.pk)])
        except DomainError as error:
            if error.status!=403: raise
            continue
        visible.append(view(row,metadata=True))
        if len(visible)>limit: break
    return dict(items=visible[:limit],next_cursor=visible[limit-1]['id'] if len(visible)>limit else 0)

def builtin_snapshot():
    definition = default_definition()
    digest = hashlib.sha256(json.dumps(dict(name='Default', definition=definition),
        sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return dict(origin='builtin', version_id=0, name='Default', sha256=digest, definition=definition)
