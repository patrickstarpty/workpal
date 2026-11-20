from django import forms
from workpal.actions.schemas import StructuredField
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from .contracts import DEFINITION, validate_definition, obj
from . import service
class Create(forms.Form):
    name=forms.CharField(max_length=200,strip=False)
    definition=StructuredField(schema=DEFINITION,validators=[validate_definition],required=False)
    def clean_name(self):
        value=self.cleaned_data['name']
        if not value.strip(): raise forms.ValidationError('Name required.')
        return value
class Select(forms.Form):
    draft_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER)
class VersionSelect(forms.Form):
    version_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER)
class Update(Select,Create):
    name=forms.CharField(max_length=200,strip=False,required=False)
    def clean(self):
        data=super().clean()
        for key in ('name','definition'):
            if key not in self.data: data.pop(key,None)
        return data
    def clean_name(self):
        if 'name' not in self.data: return ''
        return super().clean_name()
class List(forms.Form):
    cursor=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER,required=False)
    limit=forms.IntegerField(min_value=1,max_value=200,required=False)
STR={'type':'string'}
INT={'type':'integer'}
META=obj(dict(id=INT,name=STR,revision=INT,version_id=INT,created_at=STR,updated_at=STR))
VIEW=obj({**META['properties'],'definition':DEFINITION})
VERSION=obj(dict(id=INT,name=STR,draft_id=INT,number=INT,sha256=STR,published_by=INT,published_at=STR,definition=DEFINITION))
def register_actions():
    from workpal.actions.registry import register
    for action,form in [('create',Create),('read',Select),('list',List),('update',Update),('publish',Select),('version.read',VersionSelect)]:
        version=action in ('publish','version.read')
        def handler(actor,payload,revision,action=action,version=version):
            if action=='list': data=service.list(actor,cursor=payload['cursor'] or 0,limit=payload['limit'] or 50)
            elif action=='version.read': data=service.read_version(actor,**payload)
            elif action in ('publish','update'): data=getattr(service,action)(actor,revision=revision,**payload)
            else: data=getattr(service,action)(actor,**payload)
            refs=[service.ref(r['id']) for r in data['items']] if action=='list' else [service.ref(data['id'],version)]
            return ActionResult('completed',refs,data)
        def resolve(actor,payload,action=action):
            if action in ('create','list'): return ()
            version=action=='version.read'
            pk=payload['version_id' if version else 'draft_id']
            service.selected(actor,pk,version=version)
            return [service.ref(pk,version)]
        write=action in ('create','update','publish')
        register(ActionSpec('workflow.'+action,form,obj(dict(items=dict(type='array',items=META),next_cursor=INT)) if action=='list' else VERSION if version else VIEW,handler,resolve,capability='publish' if action=='publish' else 'write' if write else 'read',allowed_roles=('owner','admin') if write else ('owner','admin','member'),mutating=write,revision_required=action in ('update','publish'),audit_fields=tuple(form.base_fields)))
