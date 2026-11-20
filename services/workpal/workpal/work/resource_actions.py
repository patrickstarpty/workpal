from copy import deepcopy
from django import forms
from workpal.actions.schemas import StructuredField
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult
from .actions import Select as ProjectSelect, obj
from . import resources as service
from . import service as projects
from workpal.storage import MAX_SQLITE_INTEGER

SOURCES={'type':'array','maxItems':50,'items':obj({'kind':{'type':'string','minLength':1},'id':{'type':'string','minLength':1}})}
class Select(ProjectSelect):
    resource_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER)
class Fields(forms.Form):
    label=forms.CharField(max_length=200,strip=False)
    provider=forms.ChoiceField(choices=[('github','github'),('azure_repos','azure_repos')])
    repository_ref=forms.CharField(max_length=2000,strip=False)
    checkout_ref=forms.CharField(max_length=500,required=False,strip=False)
    source_refs=StructuredField(schema=SOURCES,required=False)
    def clean(self):
        data=super().clean()
        for k in ('checkout_ref','source_refs'):
            if k not in self.data: data.pop(k,None)
        return data
class Create(ProjectSelect,Fields): pass

def optional(field):
    field = deepcopy(field)
    field.required = False
    return field

class Update(Select,Fields):
    label = optional(Fields.base_fields['label'])
    provider = optional(Fields.base_fields['provider'])
    repository_ref = optional(Fields.base_fields['repository_ref'])
    checkout_ref = optional(Fields.base_fields['checkout_ref'])
    def clean(self):
        data=super().clean()
        return {k:v for k,v in data.items() if k in self.data}
class List(ProjectSelect):
    include_archived=forms.BooleanField(required=False)
    cursor=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER,required=False)
    limit=forms.IntegerField(min_value=1,max_value=200,required=False)
VIEW=obj({**{k:{'type':'string'} for k in ('label','provider','repository_ref','checkout_ref','verification_status','created_at','updated_at')},**{k:{'type':'integer'} for k in ('id','project_id','revision')},'archived':{'type':'boolean'}})
def resolve(actor,payload):
    p=projects.selected(actor,payload['project_id'])
    refs=[projects.ref(p.pk)]
    if 'resource_id' in payload:
        r=service.selected(actor,p.pk,payload['resource_id']); refs.append(service.ref(r.pk))
    refs.extend(service.sources(payload.get('source_refs',[])))
    return refs
def handler(action):
    def run(actor,payload,revision):
        if action=='create': data=service.create(actor,**payload)
        elif action=='read': data=service.read(actor,**payload)
        elif action=='list': data=service.list_resources(actor,**{**payload,'cursor':payload['cursor'] or 0,'limit':payload['limit'] or 50})
        elif action=='update': data=service.update(actor,revision=revision,**payload)
        else: data=service.set_archived(actor,revision=revision,archived=action=='remove',**payload)
        refs=[service.ref(r['id']) for r in data['items']] if action=='list' else [service.ref(data['id'])]
        return ActionResult('completed',refs,data)
    return run
def register_actions():
    from workpal.actions.registry import register
    for action,form in [('create',Create),('read',Select),('list',List),('update',Update),('remove',Select),('restore',Select)]:
        write=action not in ('read','list')
        register(ActionSpec('resource.'+action,form,obj({'items':{'type':'array','items':VIEW},'next_cursor':{'type':'integer'}}) if action=='list' else VIEW,handler(action),resolve,capability='write' if write else 'read',allowed_roles=('owner','admin') if write else ('owner','admin','member'),mutating=write,confirmation_required=action=='remove',revision_required=action in ('update','remove','restore'),audit_fields=tuple(form.base_fields)))
