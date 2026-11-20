"""Forms and DTO adapters for project actions."""
from django import forms
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from . import service

class Create(forms.Form):
    name = forms.CharField(max_length=200, strip=False)
    description = forms.CharField(max_length=10000, required=False, strip=False)
class Select(forms.Form):
    project_id = forms.IntegerField(min_value=1, max_value=MAX_SQLITE_INTEGER)
class Update(Select, Create):
    def clean(self):
        cleaned = super().clean()
        if 'description' not in self.data:
            cleaned.pop('description', None)
        return cleaned
class List(forms.Form):
    query = forms.CharField(max_length=200, required=False, strip=False)
    include_archived = forms.BooleanField(required=False)
    cursor = forms.IntegerField(min_value=0, max_value=MAX_SQLITE_INTEGER, required=False)
    limit = forms.IntegerField(min_value=1, max_value=200, required=False)

def obj(props):
    return dict(type='object', properties=props, required=list(props), additionalProperties=False)
VIEW = obj({**{k: {'type':'string'} for k in ('name','description','created_at','updated_at')},
            **{k: {'type':'integer'} for k in ('id','revision','workflow_version_id')}, 'archived':{'type':'boolean'}})

def handler(action):
    def run(actor, payload, revision):
        if action == 'create':
            data = service.create(actor, **payload)
        elif action == 'list':
            data = service.list_projects(actor, **{**payload, 'cursor':payload['cursor'] or 0, 'limit':payload['limit'] or 50})
        elif action == 'read':
            data = service.read(actor, payload['project_id'])
        else:
            changes = ({k:payload[k] for k in ('name','description') if k in payload} if action == 'update'
                       else {'archived':action == 'archive'})
            data = service.update(actor, payload['project_id'], revision, **changes)
        refs = [service.ref(p['id']) for p in data['items']] if action == 'list' else [service.ref(data['id'])]
        return ActionResult('completed', refs, data)
    return run

def resolve(actor, payload):
    p = service.selected(actor, payload['project_id'])
    return [service.ref(p.pk)]

def register_actions():
    from workpal.actions.registry import register
    for action, form in (('create',Create),('read',Select),('list',List),('update',Update),('archive',Select),('restore',Select)):
        write = action not in ('read','list')
        register(ActionSpec('project.'+action, form,
            obj({'items':{'type':'array','items':VIEW},'next_cursor':{'type':'integer'}}) if action=='list' else VIEW,
            handler(action), resolve if action in ('read','update','archive','restore') else lambda a,p: (),
            capability='write' if write else 'read', allowed_roles=('owner','admin') if write else ('owner','admin','member'),
            mutating=write, revision_required=action in ('update','archive','restore'), audit_fields=tuple(form.base_fields)))
    register_workflow_actions()

class SetWorkflow(Select):
    workflow_version_id = forms.IntegerField(min_value=0, max_value=MAX_SQLITE_INTEGER)

def register_workflow_actions():
    from workpal.actions.registry import register
    from workpal.workflows.contracts import DEFINITION
    snapshot = obj(dict(origin=dict(type='string', enum=['builtin','published']),
        version_id=dict(type='integer'), name=dict(type='string'),
        sha256=dict(type='string'), definition=DEFINITION))
    for binding in (True, False):
        def resolve_workflow(actor, payload, binding=binding):
            return service.workflow_refs(actor, payload['project_id'],
                payload['workflow_version_id'] if binding else None,
                'write' if binding else 'read')
        def run(actor, payload, revision, binding=binding):
            data = service.set_workflow(actor, revision=revision, **payload) if binding else service.snapshot_workflow(actor, **payload)
            return ActionResult('completed', resolve_workflow(actor, payload), data)
        register(ActionSpec('project.set_workflow' if binding else 'project.workflow.read',
            SetWorkflow if binding else Select, VIEW if binding else snapshot, run, resolve_workflow,
            capability='write' if binding else 'read',
            allowed_roles=('owner','admin') if binding else ('owner','admin','member'),
            mutating=binding, revision_required=binding, confirmation_required=binding,
            audit_fields=('project_id','workflow_version_id') if binding else ('project_id',)))
