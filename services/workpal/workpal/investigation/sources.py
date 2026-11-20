from workpal.contracts import ObjectRef,DomainError
from workpal.access.service import register_object,authorize
from workpal.storage import atomic_write
from . import environments as env,service
from .models import Source

def source_ref(pk): return ObjectRef('evidence_source',str(pk))
def create_upload(actor,environment_id,name,allowed_services):
    env.integer(environment_id)
    def write():
        env.projects.manage(actor); env.selected(actor,environment_id,'write'); env.text(name,200)
        if type(allowed_services) not in (list,tuple) or not allowed_services or len(allowed_services)>200 or any(type(x) is not int or not 1<=x<=env.MAX_SQLITE_INTEGER for x in allowed_services) or len(set(allowed_services))!=len(allowed_services): raise DomainError('invalid_input','Invalid services.')
        for pk in allowed_services:
            if service.read_service(actor,pk)['environment_id']!=environment_id: raise DomainError('invalid_input','Service environment mismatch.')
        s=Source.objects.create(environment_id=environment_id,name=name)
        s.allowed_services.set(allowed_services)
        register_object(actor.workspace_id,source_ref(s.pk),[env.ref(environment_id),*[service.service_ref(x) for x in allowed_services]])
        return read_source(actor,s.pk)
    return atomic_write(write)
def read_source(actor,source_id):
    env.integer(source_id)
    s=Source.objects.filter(pk=source_id,environment__workspace_id=actor.workspace_id).first()
    if s is None: raise DomainError('not_found','Source unavailable.',status=404)
    authorize(actor,'read',[source_ref(s.pk)])
    return dict(id=s.pk,environment_id=s.environment_id,name=s.name,adapter_type=s.adapter_type,allowed_services=list(s.allowed_services.order_by('pk').values_list('pk',flat=True)))

def create_query(actor,environment_id,name,allowed_services):
    env.integer(environment_id)
    def write():
        env.projects.manage(actor); env.selected(actor,environment_id,'write'); env.text(name,200)
        if type(allowed_services) not in (list,tuple) or not allowed_services or len(allowed_services)>200 or any(type(x) is not int or not 1<=x<=env.MAX_SQLITE_INTEGER for x in allowed_services) or len(set(allowed_services))!=len(allowed_services): raise DomainError('invalid_input','Invalid services.')
        for pk in allowed_services:
            if service.read_service(actor,pk)['environment_id']!=environment_id: raise DomainError('invalid_input','Service environment mismatch.')
            authorize(actor,'write',[service.service_ref(pk)])
        s=Source.objects.create(environment_id=environment_id,name=name,adapter_type='http_query')
        s.allowed_services.set(allowed_services)
        register_object(actor.workspace_id,source_ref(s.pk),[env.ref(environment_id),*[service.service_ref(x) for x in allowed_services]])
        return read_source(actor,s.pk)
    return atomic_write(write)
