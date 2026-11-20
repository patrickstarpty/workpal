"""Thin Registry adapters for graph persistence."""
from django import forms
from workpal.actions.schemas import StructuredField
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from .contracts import obj
from . import persistence as p

S={'type':'string'}
I={'type':'integer'}
def array(item): return dict(type='array',items=item)
CONDITION=obj(dict(field=S,op=S,value={}))
CONDITION['required']=['field','op']
CONFIG=obj(dict(mode=S,reviewer_roles=array(S),agent_id=I,input_refs=array(S),title=S,description=S,condition=CONDITION))
CONFIG['required']=[]
EDGE=obj({'from':S,'to':S,'on':S,'required':{'type':'boolean'},'max_traversals':I})
DEFINITION=obj(dict(nodes=array(obj(dict(id=S,type=S,config=CONFIG))),edges=array(EDGE),declared_fields=array(S)))
META=obj(dict(id=I,name=S,revision=I,current_version_id=I))
VIEW=obj({**META['properties'],'definition':DEFINITION})
INPUT=obj(dict(node_id=S,agent_id=I,input_refs=array(obj(dict(kind=S,id=S)))))
VERSION=obj(dict(id=I,draft_id=I,number=I,name=S,graph=obj(dict(schema_version=I,definition=DEFINITION,sha256=S)),resolved_inputs=array(INPUT),published_by=I,published_at=S))
class Create(forms.Form):
    name=forms.CharField(max_length=200,strip=False)
    definition=StructuredField(schema=DEFINITION)
class Select(forms.Form):
    draft_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER)
class Update(Select,Create): pass
class VersionSelect(forms.Form):
    version_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER)
class List(forms.Form):
    cursor=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER,required=False)
    limit=forms.IntegerField(min_value=1,max_value=200,required=False)

def register_actions():
    from workpal.actions.registry import register
    for action,form in [('create',Create),('read',Select),('list',List),('update',Update),('publish',Select),('version.read',VersionSelect)]:
        write=action in ('create','update','publish')
        capability='publish' if action=='publish' else 'write' if action=='update' else 'read'
        def resolve(actor,payload,action=action,capability=capability):
            if action in ('create','update','publish'): p.manage(actor)
            refs=[]
            if action not in ('create','list'):
                version=action=='version.read'
                pk=payload['version_id' if version else 'draft_id']
                row=p.selected(actor,pk,capability,version)
                refs.append(p.ref(pk,version))
                if action=='publish': refs.extend(p.inputs(actor,row.definition,capability)[0])
            if action in ('create','update'):
                graph=p.normalized(payload['name'],payload['definition'])
                refs.extend(p.inputs(actor,graph['definition'],capability)[0])
            return refs
        def handler(actor,payload,revision,action=action):
            if action=='list': data=p.list_drafts(actor,payload['cursor'] if payload['cursor'] is not None else 0,payload['limit'] if payload['limit'] is not None else 50)
            elif action=='version.read': data=p.read_version(actor,**payload)
            elif action in ('update','publish'): data=getattr(p,action)(actor,revision=revision,**payload)
            else: data=getattr(p,action)(actor,**payload)
            return ActionResult('completed',[],data)
        def results(actor,result,action=action):
            if action=='list':
                return [p.ref(p.selected(actor,item['id']).pk) for item in result.data['items']]
            version=action in ('publish','version.read')
            row=p.selected(actor,result.data['id'],version=version)
            if version and row.draft_id!=result.data['draft_id']: p.invalid()
            return [p.ref(row.pk,version)]
        register(ActionSpec('workflow_graph.'+action,form,
            obj(dict(items=array(META),next_cursor=I)) if action=='list' else VERSION if action in ('publish','version.read') else VIEW,
            handler,resolve,capability=capability,allowed_roles=('owner','admin') if write else ('owner','admin','member'),
            mutating=write,revision_required=action in ('update','publish'),result_refs=results,
            audit_fields=tuple(k for k in form.base_fields if k in ('draft_id','version_id','cursor','limit'))))
