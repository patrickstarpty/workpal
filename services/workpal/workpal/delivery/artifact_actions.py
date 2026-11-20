from django import forms
from workpal.actions.contracts import ActionSpec
from workpal.actions.schemas import StructuredField
from workpal.contracts import ActionResult
from workpal.storage import MAX_SQLITE_INTEGER
from . import artifacts as service

def obj(properties, required=None):
    return dict(type='object', properties=properties, required=list(properties) if required is None else required, additionalProperties=False)
SOURCES = dict(type='array', maxItems=50, items=obj({'kind':dict(type='string', minLength=1, maxLength=100), 'id':dict(type='string', minLength=1, maxLength=255)}))
class Begin(forms.Form):
    filename = forms.CharField(max_length=255, strip=False)
    size = forms.IntegerField(min_value=0, max_value=service.MAX_SIZE)
    media_type = forms.CharField(max_length=127, required=False, strip=False)
    source_refs = StructuredField(schema=SOURCES, required=False)
    def clean(self):
        data = super().clean()
        return {k:v for k,v in data.items() if k in self.data}
class Read(forms.Form):
    upload_id = forms.IntegerField(min_value=1, max_value=MAX_SQLITE_INTEGER)
VIEW = obj({**{k:dict(type='string') for k in ('filename','media_type','status','created_at')}, **{k:dict(type='integer') for k in ('id','size','offset','artifact_id')}})
def resolve_begin(actor, payload):
    fields, refs = service.validate_metadata(payload)
    return refs

def resolve_read(actor, payload):
    return [service.ref(service.selected(actor, payload['upload_id']).pk)]

def _register_upload_actions():
    from workpal.actions.registry import register
    for action, form, resolver in [('begin', Begin, resolve_begin), ('read', Read, resolve_read)]:
        def handler(actor, payload, revision, action=action):
            data = service.begin(actor, payload) if action == 'begin' else service.status(actor, payload['upload_id'])
            return ActionResult('completed', [service.ref(data['id'])], data)
        register(ActionSpec('artifact.upload.'+action, form, VIEW, handler, resolver,
                            capability='write' if action=='begin' else 'read', mutating=action=='begin',
                            audit_fields=tuple(form.base_fields)))

class Finish(Read):
    sha256 = forms.CharField(min_length=64, max_length=64, strip=False)
class ArtifactRead(forms.Form):
    artifact_id = forms.IntegerField(min_value=1, max_value=MAX_SQLITE_INTEGER)
ARTIFACT_VIEW = obj({**{k:dict(type='string') for k in ('filename','media_type','sha256','created_at')}, **{k:dict(type='integer') for k in ('id','size','owner_user_id')}})
def register_actions():
    from workpal.actions.registry import register
    _register_upload_actions()
    def resolve_finish(actor, payload):
        u = service.selected(actor, payload['upload_id'], 'write')
        if u.artifact_id: service.read(actor, u.artifact_id)
        return [service.ref(u.pk)]
    def resolve_artifact(actor, payload):
        return [service.artifact_ref(service.read(actor, payload['artifact_id'])['id'])]
    def finish(actor, payload, revision):
        data = service.finish(actor, **payload)
        return ActionResult('completed', [service.artifact_ref(data['id'])], data)
    def read(actor, payload, revision):
        data = service.read(actor, **payload)
        return ActionResult('completed', [service.artifact_ref(data['id'])], data)
    register(ActionSpec('artifact.upload.finish', Finish, ARTIFACT_VIEW, finish, resolve_finish, capability='write', mutating=True, audit_fields=('upload_id','sha256')))
    register(ActionSpec('artifact.read', ArtifactRead, ARTIFACT_VIEW, read, resolve_artifact, capability='read', mutating=False, audit_fields=('artifact_id',)))
