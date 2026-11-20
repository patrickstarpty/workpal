"""Registry adapter for restricted policy management."""
from django import forms
from workpal.actions.contracts import ActionSpec
from workpal.actions.registry import register
from workpal.actions.schemas import StructuredField
from workpal.contracts import ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work.actions import obj
from . import evidence, sources

POLICY=obj(dict(version={'type':'integer','enum':[1]},allow_text={'type':'boolean'},allow_fields={'type':'array','items':{'type':'string','minLength':1,'maxLength':128},'maxItems':100},redact_literals={'type':'array','items':{'type':'string','minLength':1,'maxLength':256},'maxItems':100}))
META=dict(source_id={'type':'integer'},revision={'type':'integer'},policy_sha256={'type':'string'})

class EvidenceListForm(forms.Form):
    investigation_id = forms.IntegerField(min_value=1, max_value=MAX_SQLITE_INTEGER)
    cursor = forms.IntegerField(min_value=0, max_value=MAX_SQLITE_INTEGER, required=False)
    limit = forms.IntegerField(min_value=1, max_value=200, required=False)

    def clean(self):
        data = super().clean()
        for field, default in (('cursor', 0), ('limit', 50)):
            if data.get(field) is None:
                data[field] = default
        return data

def resolve(actor,payload):
    source=evidence.selected(actor,payload['source_id'])
    return [sources.source_ref(source.pk)]

def register_actions():
    for write in (True,False):
        fields=dict(source_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER))
        if write: fields['policy']=StructuredField(schema=POLICY)
        form=type('EvidencePolicyForm',(forms.Form,),fields)
        output=obj(META) if write else dict(type='object',properties=dict(META,configured={'type':'boolean'},policy=POLICY),required=[*META,'configured'],additionalProperties=False)
        def handler(actor,payload,revision,write=write):
            data=evidence.configure_policy(actor,**payload,expected_revision=revision) if write else evidence.read_policy(actor,**payload)
            return ActionResult('completed',[sources.source_ref(payload['source_id'])],data)
        register(ActionSpec('evidence_policy.'+('configure' if write else 'read'),form,output,handler,resolve,capability='publish',allowed_roles=('owner','admin'),mutating=write,confirmation_required=write,revision_required=write,audit_fields=('source_id',)))

    fields={name:forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER) for name in ('investigation_id','source_id')}
    fields['raw_bytes']=forms.IntegerField(min_value=0,max_value=2097152)
    for name in ('format','raw_sha256','timezone','range_start','range_end'):
        fields[name]=forms.CharField(required=name in ('format','raw_sha256'),max_length=100)
    upload_form=type('EvidenceUploadForm',(forms.Form,),fields)
    integers='id investigation_id environment_id service_id source_id actor_id policy_revision raw_bytes content_bytes total_records included_records redaction_count omitted_fields'.split()
    strings='created_at timezone origin coverage format status raw_sha256 content_sha256 policy_sha256'.split()
    props={name:{'type':'integer'} for name in integers}
    props.update({name:{'type':'string'} for name in strings})
    props.update({name:{'type':'null'} for name in ('event_time','deployment_id','commit_sha','original_location')})
    props.update(range_start={'type':['string','null'],'maxLength':64},range_end={'type':['string','null'],'maxLength':64},truncated={'type':'boolean'},included_line_numbers={'type':'array','items':{'type':'integer'}})
    def upload(actor,payload,revision):
        data=evidence._store(actor,payload)
        return ActionResult('completed',[evidence.ref(data['id'])],data)
    def read(actor,payload,revision):
        row=evidence._read(actor,payload['evidence_id'])
        return ActionResult('completed',[evidence.ref(row.pk)],dict(evidence._metadata(row),content=row.content))
    register(ActionSpec('evidence.upload',upload_form,obj(props),upload,evidence._resolve_upload,mutating=True,audit_fields=('investigation_id','source_id','format')))
    read_form=type('EvidenceReadForm',(forms.Form,),dict(evidence_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER)))
    register(ActionSpec('evidence.read',read_form,obj(dict(props,content={'type':'string'})),read,lambda actor,payload:[evidence.ref(evidence._read(actor,payload['evidence_id']).pk)],audit_fields=('evidence_id',)))
    def listing(actor,payload,revision):
        data=evidence._list(actor,**payload)
        return ActionResult('completed',[evidence.service.ref(payload['investigation_id']),*[evidence.ref(item['id']) for item in data['items']]],data)
    register(ActionSpec('evidence.list',EvidenceListForm,obj(dict(items={'type':'array','items':obj(props)},next_cursor={'type':'integer'})),listing,lambda actor,payload:[evidence.service.ref(payload['investigation_id'])],audit_fields=('investigation_id','cursor','limit')))
