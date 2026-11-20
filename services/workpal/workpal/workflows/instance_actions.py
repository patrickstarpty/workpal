"""Closed Registry adapters for initialization and historical read."""
from django import forms
from workpal.actions.schemas import StructuredField
from workpal.actions.contracts import ActionSpec
from workpal.contracts import SubjectRef, ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work.issue_actions import VIEW as ISSUE, HISTORY
from workpal.agents.actions import VIEW as AGENT
from .graph_actions import obj, S, I, array, VERSION
from . import instances as business

SUBJECT=obj(dict(type=S,id=S))
SNAPSHOT=obj(dict(schema_version=I,graph_version=VERSION,issue=ISSUE,requirements=HISTORY,agents=array(AGENT),source_refs=array(obj(dict(kind=S,id=S))),created_by=I))
VIEW=obj(dict(id=I,version_id=I,subject=SUBJECT,state=S,snapshot=SNAPSHOT,sha256=S,created_at=S))
class Initialize(forms.Form):
    subject=StructuredField(schema=SUBJECT)
    version_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER)
class Read(forms.Form):
    instance_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER)

def register_actions():
    register_listing()
    from workpal.actions.registry import register
    for name,form in [('initialize',Initialize),('read',Read)]:
        def resolve(actor,payload,name=name):
            if name=='initialize': return business.resolve(actor,SubjectRef(**payload['subject']),payload['version_id'])[1]
            return [business.ref(business.selected(actor,payload['instance_id']).pk)]
        def handler(actor,payload,revision,name=name):
            data=business.create_record(actor,SubjectRef(**payload['subject']),payload['version_id']) if name=='initialize' else business.read(actor,**payload)
            return ActionResult('completed',[business.ref(data['id'])],data)
        def results(actor,result,name=name):
            row=business.selected(actor,result.data['id'])
            if business.view(row)!=result.data: business.p.invalid()
            if name=='initialize': business.resolve(actor,SubjectRef(**result.data['subject']),row.version_id)
            return [business.ref(row.pk)]
        register(ActionSpec('workflow_graph.instance.'+name,form,VIEW,handler,resolve,capability='read',allowed_roles=('owner','admin','member'),mutating=name=='initialize',result_refs=results,audit_fields=('version_id',) if name=='initialize' else ('instance_id',)))

SUMMARY=obj({key:value for key,value in VIEW['properties'].items() if key!='snapshot'})
class List(forms.Form):
    cursor=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER-1,required=False)
    limit=forms.IntegerField(min_value=1,max_value=200,required=False)

    def clean(self):
        data=super().clean()
        for key,default in (('cursor',0),('limit',50)):
            if data.get(key) is None: data[key]=default
        return data


def register_listing():
    from workpal.actions.registry import register
    def handler(actor,payload,revision):
        return ActionResult('completed',[],business.list_instances(actor,**payload))
    def results(actor,result):
        refs=[]
        for item in result.data['items']:
            row=business.selected(actor,item['id'])
            if business.summary(row)!=item: business.p.invalid()
            refs.append(business.ref(row.pk))
        return refs
    register(ActionSpec('workflow_graph.instance.list',List,obj(dict(items=array(SUMMARY),next_cursor=I)),handler,lambda actor,payload:[],capability='read',allowed_roles=('owner','admin','member'),mutating=False,result_refs=results,audit_fields=('cursor','limit')))
