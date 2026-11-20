from workpal.contracts import DomainError,ObjectRef
from workpal.access.service import authorize,register_object
from workpal.storage import atomic_write
from . import environments as env
from .models import Service,Investigation,Source

def service_ref(pk): return ObjectRef('environment_service',str(pk))
def ref(pk): return ObjectRef('investigation',str(pk))
def create_service(actor,environment_id,name):
    env.integer(environment_id)
    def write():
        env.projects.manage(actor); env.selected(actor,environment_id,'write'); env.text(name,200)
        s=Service.objects.create(environment_id=environment_id,name=name)
        register_object(actor.workspace_id,service_ref(s.pk),[env.ref(environment_id)])
        return read_service(actor,s.pk)
    return atomic_write(write)
def read_service(actor,service_id):
    env.integer(service_id)
    s=Service.objects.filter(pk=service_id,environment__workspace_id=actor.workspace_id).first()
    if s is None: raise DomainError('not_found','Service unavailable.',status=404)
    authorize(actor,'read',[service_ref(s.pk)])
    return dict(id=s.pk,environment_id=s.environment_id,name=s.name)
def list_services(actor,environment_id,cursor=0,limit=50):
    env.read(actor,environment_id)
    return env.page(actor,Service.objects.filter(environment_id=environment_id),read_service,cursor,limit)
def view(i): return dict(id=i.pk,project_id=i.project_id,environment_id=i.environment_id,service_id=i.service_id,problem=i.problem,revision=i.revision,status=i.status,created_at=i.created_at.isoformat(),query_budget=10,window_minutes=30)
def read(actor,investigation_id):
    env.integer(investigation_id)
    i=Investigation.objects.filter(pk=investigation_id,workspace_id=actor.workspace_id).first()
    if i is None: raise DomainError('not_found','Investigation unavailable.',status=404)
    authorize(actor,'read',[ref(i.pk)]); return view(i)
def start(actor,project_id,environment_id,service_id,problem,key):
    env.integer(project_id); env.integer(environment_id); env.integer(service_id)
    def write():
        e=env.selected(actor,environment_id,'write'); env.text(problem,8000); env.text(key,200)
        s=read_service(actor,service_id)
        if e.project_id!=project_id or s['environment_id']!=environment_id: raise DomainError('invalid_input','Environment/service mismatch.')
        from .sources import source_ref
        refs=[source_ref(x.pk) for x in Source.objects.filter(environment_id=environment_id,allowed_services=service_id)]
        authorize(actor,'read',refs)
        old=Investigation.objects.filter(workspace_id=actor.workspace_id,actor_id=actor.user_id,key=key).first()
        if old:
            if (old.project_id,old.environment_id,old.service_id,old.problem)!=(project_id,environment_id,service_id,problem): raise DomainError('idempotency_conflict','Key already used.',status=409)
            return read(actor,old.pk)
        i=Investigation.objects.create(workspace_id=actor.workspace_id,actor_id=actor.user_id,project_id=project_id,environment_id=environment_id,service_id=service_id,problem=problem,key=key)
        register_object(actor.workspace_id,ref(i.pk),[env.ref(environment_id),env.projects.ref(project_id),service_ref(service_id),*refs])
        return read(actor,i.pk)
    return atomic_write(write)
def list_investigations(actor,project_id,environment_id=None,cursor=0,limit=50):
    env.integer(project_id)
    if environment_id is not None: env.integer(environment_id)
    env.projects.read(actor,project_id)
    rows=Investigation.objects.filter(project_id=project_id,workspace_id=actor.workspace_id)
    if environment_id is not None: rows=rows.filter(environment_id=environment_id)
    return env.page(actor,rows,read,cursor,limit)
