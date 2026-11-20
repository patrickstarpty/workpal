"""Registry adapter for restricted policy management."""
from django import forms
from workpal.actions.contracts import ActionSpec
from workpal.actions.registry import register
from workpal.actions.schemas import StructuredField
from workpal.contracts import ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from workpal.work.actions import obj
from . import query_config as evidence, sources

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
    if 'config' in payload: evidence.validate(payload['config'])
    if 'policy' in payload: evidence._policy(payload['policy'])
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
        register(ActionSpec('query_policy.'+('configure' if write else 'read'),form,output,handler,resolve,capability='publish',allowed_roles=('owner','admin'),mutating=write,confirmation_required=write,revision_required=write,audit_fields=('source_id',)))

    for write in (True,False):
        fields=dict(source_id=forms.IntegerField(min_value=1,max_value=MAX_SQLITE_INTEGER))
        if write: fields['config']=StructuredField(schema=__import__('workpal.investigation.query_contracts',fromlist=['CONFIG']).CONFIG)
        form=type('QueryConfigForm',(forms.Form,),fields)
        meta=dict(source_id={'type':'integer'},revision={'type':'integer'},config_sha256={'type':'string'})
        def handler(actor,payload,revision,write=write):
            data=evidence.configure(actor,**payload,expected_revision=revision) if write else evidence.read_config(actor,**payload)
            return ActionResult('completed',[sources.source_ref(payload['source_id'])],data)
        register(ActionSpec('query_config.'+('configure' if write else 'read'),form,obj(meta if write else dict(meta,configured={'type':'boolean'},connected={'type':'boolean'})),handler,resolve,capability='publish',allowed_roles=('owner','admin'),mutating=write,confirmation_required=write,revision_required=write,audit_fields=('source_id',)))
