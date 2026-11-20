from workpal.actions.schemas import StructuredField
from django import forms
from workpal.contracts import ObjectRef
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.actions.contracts import ActionSpec
from workpal.actions.registry import register
from workpal.contracts import ActionResult
from . import environments as e,service as s,sources as src
from workpal.work.actions import obj

def integer(required=True): return forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER,required=required)
def string(maximum): return forms.CharField(max_length=maximum,strip=False)
def schema(fields):
    types={'id':'integer','project_id':'integer','environment_id':'integer','service_id':'integer','revision':'integer','query_budget':'integer','window_minutes':'integer'}
    return obj({k:({'type':'array','items':{'type':'integer'}} if k=='allowed_services' else {'type':types.get(k,'string')}) for k in fields.split()})
EV=schema('id project_id name timezone revision'); SV=schema('id environment_id name'); SOURCE=schema('id environment_id name adapter_type allowed_services'); IV=schema('id project_id environment_id service_id problem revision status created_at query_budget window_minutes')
def register_actions():
    definitions=[
      ('environment.create',e.create,dict(project_id=integer(),name=string(200),timezone=string(100),source_refs=StructuredField(required=False,schema={'type':'array','items':obj({'kind':{'type':'string'},'id':{'type':'string'}}),'maxItems':200})),EV,'environment',True),
      ('environment.read',e.read,dict(environment_id=integer()),EV,'environment',False),
      ('environment.list',e.list_environments,dict(project_id=integer()),EV,'environment',False),
      ('environment.ensure_defaults',e.ensure_defaults,dict(project_id=integer(),timezone=string(100)),EV,'environment',True),
      ('environment.grant',e.grant,dict(environment_id=integer(),user_id=integer(),read=forms.BooleanField(required=False),write=forms.BooleanField(required=False),publish=forms.BooleanField(required=False)),EV,'environment',True),
      ('environment_service.create',s.create_service,dict(environment_id=integer(),name=string(200)),SV,'environment_service',True),
      ('environment_service.read',s.read_service,dict(service_id=integer()),SV,'environment_service',False),
      ('environment_service.list',s.list_services,dict(environment_id=integer()),SV,'environment_service',False),
      ('evidence_source.create_query',src.create_query,dict(environment_id=integer(),name=string(200),allowed_services=StructuredField(schema={'type':'array','items':{'type':'integer','minimum':1},'minItems':1,'maxItems':200})),SOURCE,'evidence_source',True),
      ('evidence_source.create_upload',src.create_upload,dict(environment_id=integer(),name=string(200),allowed_services=StructuredField(schema={'type':'array','items':{'type':'integer','minimum':1},'minItems':1,'maxItems':200})),SOURCE,'evidence_source',True),
      ('evidence_source.read',src.read_source,dict(source_id=integer()),SOURCE,'evidence_source',False),
      ('investigation.start',s.start,dict(project_id=integer(),environment_id=integer(),service_id=integer(),problem=string(8000),key=string(200)),IV,'investigation',True),
      ('investigation.read',s.read,dict(investigation_id=integer()),IV,'investigation',False),
      ('investigation.list',s.list_investigations,dict(project_id=integer(),environment_id=integer(False)),IV,'investigation',False)]
    for action,fn,fields,output,kind,write in definitions:
        listing=action.endswith('.list'); defaults=action.endswith('ensure_defaults'); grant=action.endswith('.grant')
        if listing: fields.update(cursor=forms.IntegerField(min_value=0,max_value=MAX_SQLITE_INTEGER,required=False),limit=forms.IntegerField(min_value=1,max_value=200,required=False))
        form=type(action.replace('.','_'),(forms.Form,),fields)
        def handler(actor,payload,revision,fn=fn,kind=kind,listing=listing,defaults=defaults,grant=grant):
            payload=dict(payload)
            if listing: payload.update(cursor=payload.get('cursor') or 0,limit=payload.get('limit') or 50)
            if grant: payload['revision']=revision
            if 'source_refs' in payload: payload['source_refs']=tuple(ObjectRef(**r) for r in (payload['source_refs'] or []))
            data=fn(actor,**payload)
            if grant: return ActionResult('completed',[],{})
            if defaults: data=dict(items=data,next_cursor=0)
            rows=data['items'] if listing or defaults else [data]
            return ActionResult('completed',[ObjectRef(kind,str(x['id'])) for x in rows],data)
        register(ActionSpec(action,form,obj(dict(items={'type':'array','items':output},next_cursor={'type':'integer'})) if listing or defaults else (obj({}) if grant else output),handler,resolver(action,write),capability=('publish' if grant else 'write' if write else 'read'),mutating=write,confirmation_required=grant,revision_required=grant,audit_fields=tuple(k for k in fields if k not in ('problem','key')),allowed_roles=('owner','admin') if write and action!='investigation.start' else ('owner','admin','member')))

    from . import query_actions
    query_actions.register_actions()

def resolver(action,write):
    def resolve(actor,payload):
        refs=[]
        for key,kind in (('project_id','project'),('environment_id','environment'),('service_id','environment_service'),('source_id','evidence_source'),('investigation_id','investigation')):
            if payload.get(key) is not None: refs.append(ObjectRef(kind,str(payload[key])))
        refs.extend(ObjectRef(**r) for r in (payload.get('source_refs') or []))
        refs.extend(ObjectRef('environment_service',str(pk)) for pk in payload.get('allowed_services',[]))
        if action=='investigation.start':
            from .models import Source
            source_refs=[src.source_ref(x.pk) for x in Source.objects.filter(environment_id=payload['environment_id'],allowed_services=payload['service_id'])]
            # Upload sources require read; the target environment requires write.
            from workpal.access.service import authorize
            authorize(actor,'read',source_refs)
            # Read-only evidence provenance is returned through the investigation
            # result; only target objects require write during admission.
        return refs
    return resolve
