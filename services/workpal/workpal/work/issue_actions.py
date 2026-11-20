"""Strict Registry adapters for Issue operations."""
from django import forms
from workpal.actions.schemas import StructuredField
from workpal.actions.contracts import ActionSpec
from workpal.contracts import ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from .actions import obj
from .resource_actions import SOURCES
from . import issues

CRITERIA={'type':'array','maxItems':100,'items':obj({'key':{'type':'string','maxLength':64},'text':{'type':'string','maxLength':2000}})}
class Select(forms.Form):
    issue_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER-1)
class Fields(forms.Form):
    title=forms.CharField(max_length=300,strip=False)
    description=forms.CharField(max_length=20000,required=False,strip=False)
    criteria=StructuredField(schema=CRITERIA,required=False)
    assignee_user_id=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER-1,required=False)
    source_refs=StructuredField(schema=SOURCES,required=False)
    def clean(self):
        data=super().clean()
        return {k:v for k,v in data.items() if k in self.data}
class Create(Fields):
    parent_issue_id=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER-1,required=False)
    project_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER-1)
class Update(Select,Fields):
    title=forms.CharField(max_length=300,strip=False,required=False)
class Requirements(Select):
    number=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER-1)
class List(forms.Form):
    parent_issue_id=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER-1,required=False)
    status_key=forms.CharField(max_length=64,required=False)
    assignee_user_id=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER-1,required=False)
    project_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER-1,required=False)
    query=forms.CharField(max_length=300,strip=False,required=False)
    include_archived=forms.BooleanField(required=False)
    cursor=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER-1,required=False)
    limit=forms.IntegerField(min_value=1,max_value=200,required=False)
    def clean(self):
        data=super().clean()
        data['cursor']=data.get('cursor') or 0; data['limit']=data.get('limit') or 50
        for k in ('status_key','assignee_user_id','parent_issue_id'):
            if k not in self.data: data.pop(k,None)
        if data.get('project_id') is None: data.pop('project_id',None)
        return data

def resolve(actor,payload):
    if 'issue_id' in payload: return [issues.ref(issues.selected(actor,payload['issue_id']).pk)]
    if 'project_id' in payload:
        parent_refs=[issues.ref(issues.selected(actor,payload['parent_issue_id']).pk)] if payload.get('parent_issue_id') else []
        return parent_refs+ issues.projects.workflow_refs(actor,payload['project_id'])+issues.sources(payload.get('source_refs',[]))
    return []
def handler(action):
    def run(actor,payload,revision):
        previous = None
        if action == 'update' and {'title', 'description', 'criteria'} & payload.keys():
            previous = issues.requirement_ref(issues.selected(actor, payload['issue_id']).current_requirements_id)
        fn={'list':issues.list_issues,'requirements.read':issues.read_requirements}.get(action) or getattr(issues,action)
        data=fn(actor,**payload,**({'revision':revision} if action in ('update','archive','restore') else {}))
        refs=[issues.ref(i['id']) for i in data['items']] if action=='list' else [issues.ref(data['issue_id'] if action=='requirements.read' else data['id'])]
        if previous is not None:
            # Keep the version actually read by this execution. Resolving the
            # current version before a cached replay would bind it to new data.
            refs.extend(dict.fromkeys([issues.requirement_ref(data['requirements_version_id']), previous]))
        return ActionResult('completed',refs,data)
    return run

from workpal.workflows.contracts import DEFINITION
STR={'type':'string'}
INT={'type':'integer'}
SNAP=obj(dict(origin=STR,version_id=INT,name=STR,sha256=STR,definition=DEFINITION))
PROPS={**{k:INT for k in ('id','parent_issue_id','project_id','assignee_user_id','revision','requirements_version_id','requirements_revision')},**{k:STR for k in ('title','description','status_key','created_at','updated_at')},'criteria':CRITERIA,'archived':{'type':'boolean'}}
PROPS.update(status_category=STR,lifecycle=STR,blocked_reason=STR,blocked_owner_user_id=INT)
VIEW=obj(dict(**PROPS,workflow_snapshot=SNAP))
HISTORY=obj(dict(id=INT,issue_id=INT,number=INT,title=STR,description=STR,criteria=CRITERIA,sha256=STR,created_by=INT,created_at=STR))
def register_actions():
    from workpal.actions.registry import register
    for action,form in [('create',Create),('read',Select),('update',Update),('list',List),('archive',Select),('restore',Select),('requirements.read',Requirements)]:
        write=action in ('create','update','archive','restore')
        register(ActionSpec('issue.'+action,form,(obj(dict(items={'type':'array','items':obj(PROPS)},next_cursor=INT)) if action=='list' else HISTORY if action=='requirements.read' else VIEW),handler(action),resolve,capability='write' if write else 'read',mutating=write,revision_required=action in ('update','archive','restore'),audit_fields=tuple(form.base_fields),result_refs=issues.result_refs))

class Transition(Select):
    target=forms.CharField(max_length=64,strip=False)
    reason=forms.CharField(max_length=4000,required=False,strip=False)
    blocked_owner_user_id=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER-1,required=False)
    def clean(self):
        data=super().clean(); data['blocked_owner_user_id']=data.get('blocked_owner_user_id') or 0
        return data
class Dependency(Select):
    depends_on_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER-1)
class Page(Select):
    cursor=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER-1,required=False)
    limit=forms.IntegerField(min_value=1,max_value=200,required=False)
    def clean(self):
        data=super().clean(); data['cursor']=data.get('cursor') or 0; data['limit']=data.get('limit') or 50
        return data

def register_fact_actions():
    from . import transitions, dependencies
    from workpal.actions.registry import register
    history_fields={k:STR for k in ('from_key','to_key','reason','before_blocked_reason','after_blocked_reason','workflow_sha256','created_at')}
    history_fields.update({k:INT for k in ('id','issue_id','actor_user_id','before_blocked_owner_id','after_blocked_owner_id','requirements_version_id','revision')})
    history_fields['actor_executor_id']=STR
    from workpal.delivery.approval_actions import VIEW as APPROVAL_VIEW
    history_schema = obj(history_fields)
    history_schema['properties']['approval'] = APPROVAL_VIEW
    for name,form,fn,write,schema in [
        ('transition',Transition,transitions.transition,True,VIEW),
        ('transitions.list',Page,transitions.list_transitions,False,obj(dict(items={'type':'array','items':history_schema},next_cursor=INT))),
        ('dependency.add',Dependency,dependencies.add,True,VIEW),
        ('dependency.remove',Dependency,dependencies.remove,True,VIEW),
        ('dependency.list',Page,dependencies.list_dependencies,False,obj(dict(items={'type':'array','items':obj(dict(id=INT,depends_on_id=INT,status_key=STR,status_category=STR))},next_cursor=INT)))]:
        def refs(actor,payload,name=name):
            result=resolve(actor,payload)
            if name=='transition':
                transitions.authorize_target(actor,issues.selected(actor,payload['issue_id']),payload['target'])
            if 'depends_on_id' in payload: result.append(issues.ref(issues.selected(actor,payload['depends_on_id']).pk))
            return result
        def run(actor,payload,revision,fn=fn,write=write,name=name):
            data=fn(actor,**payload,**({'revision':revision} if write else {}))
            result_refs=[issues.ref(payload['issue_id'])]
            if name=='transition':
                from .models import IssueTransition
                event = IssueTransition.objects.get(issue_id=payload['issue_id'], revision=data['revision'])
                if event.completion_snapshot:
                    result_refs.append(transitions.ref(event.pk))
            if name=='transitions.list':
                result_refs.extend(transitions.ref(item['id']) for item in data['items'])
            return ActionResult('completed',result_refs,data)
        register(ActionSpec('issue.'+name,form,schema,run,refs,capability='write' if write else 'read',mutating=write,revision_required=write,audit_fields=tuple(form.base_fields),result_refs=issues.result_refs if write else None))

class Parent(Select):
    parent_issue_id=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER-1)
class Children(Page):
    include_archived=forms.BooleanField(required=False)

def register_hierarchy_actions():
    from . import hierarchy
    from workpal.actions.registry import register
    for name,form,fn,write in [('set_parent',Parent,hierarchy.set_parent,True),('children.list',Children,hierarchy.children,False)]:
        def refs(actor,payload):
            result=[issues.ref(issues.selected(actor,payload['issue_id']).pk)]
            if payload.get('parent_issue_id'): result.append(issues.ref(issues.selected(actor,payload['parent_issue_id']).pk))
            return result
        def run(actor,payload,revision,fn=fn,write=write):
            data=fn(actor,**payload,**({'revision':revision} if write else {}))
            result=[issues.ref(payload['issue_id'])]
            if not write: result.extend(issues.ref(item['id']) for item in data['items'])
            return ActionResult('completed',result,data)
        register(ActionSpec('issue.'+name,form,VIEW if write else obj(dict(items={'type':'array','items':obj(PROPS)},next_cursor=INT)),run,refs,capability='write' if write else 'read',mutating=write,revision_required=write,audit_fields=tuple(form.base_fields),result_refs=issues.result_refs))
