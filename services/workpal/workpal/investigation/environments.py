from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from workpal.contracts import DomainError, ObjectRef
from workpal.access.service import authorize, register_object, resolve
from workpal.access.models import SourceGrant
from workpal.identity.models import Membership
from workpal.work import service as projects
from workpal.storage import atomic_write
from .models import Environment

from workpal.storage import MAX_SQLITE_INTEGER

def integer(value, minimum=1, maximum=MAX_SQLITE_INTEGER):
    if type(value) is not int or not minimum <= value <= maximum:
        raise DomainError('invalid_input','Invalid integer.')

def valid_timezone(timezone):
    text(timezone,100)
    try: ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError): raise DomainError('invalid_input','Invalid timezone.')

def ref(pk): return ObjectRef('environment',str(pk))
def text(value,maximum):
    if type(value) is not str or not value.strip() or len(value)>maximum: raise DomainError('invalid_input','Invalid text.')
def view(e): return dict(id=e.pk,project_id=e.project_id,name=e.name,timezone=e.timezone,revision=e.revision)
def selected(actor,pk,capability='read'):
    integer(pk)
    e=Environment.objects.filter(pk=pk,workspace_id=actor.workspace_id).first()
    if e is None: raise DomainError('not_found','Environment unavailable.',status=404)
    authorize(actor,capability,[ref(e.pk)])
    return e

def create(actor,project_id,name,timezone,source_refs=()):
    integer(project_id)
    valid_timezone(timezone)
    def write():
        projects.manage(actor); projects.selected(actor,project_id,'write'); text(name,200); text(timezone,100)
        try: ZoneInfo(timezone)
        except (ZoneInfoNotFoundError,ValueError): raise DomainError('invalid_input','Invalid timezone.')
        authorize(actor,'read',source_refs)
        if Environment.objects.filter(project_id=project_id,name=name).exists(): raise DomainError('conflict','Environment exists.',status=409)
        e=Environment.objects.create(workspace_id=actor.workspace_id,project_id=project_id,name=name,timezone=timezone)
        register_object(actor.workspace_id,ref(e.pk),[projects.ref(project_id),*source_refs],is_source=True)
        SourceGrant.objects.create(user_id=actor.user_id,source=resolve(ref(e.pk)),read=True,write=True,publish=True)
        return view(e)
    return atomic_write(write)
def read(actor,environment_id): return view(selected(actor,environment_id))
def page(actor,rows,read,cursor,limit):
    if type(cursor) is not int or not 0<=cursor<=MAX_SQLITE_INTEGER or type(limit) is not int or not 1<=limit<=200: raise DomainError('invalid_input','Invalid pagination.')
    visible=[]
    for row in rows.filter(pk__gt=cursor).order_by('pk'):
        try: visible.append(read(actor,row.pk))
        except DomainError as error:
            if error.status!=403: raise
        if len(visible)>limit: break
    return dict(items=visible[:limit],next_cursor=visible[limit-1]['id'] if len(visible)>limit else 0)
def list_environments(actor,project_id,cursor=0,limit=50):
    integer(project_id)
    projects.read(actor,project_id)
    return page(actor,Environment.objects.filter(project_id=project_id),read,cursor,limit)
def ensure_defaults(actor,project_id,timezone):
    integer(project_id)
    valid_timezone(timezone)
    def write():
        projects.manage(actor); projects.selected(actor,project_id,'write')
        return [read(actor,e.pk) if (e:=Environment.objects.filter(project_id=project_id,name=n).first()) else create(actor,project_id,n,timezone) for n in ('SIT','UAT','PRD')]
    return atomic_write(write)
def grant(actor,environment_id,user_id,read,write,publish,revision):
    integer(environment_id); integer(user_id); integer(revision, maximum=MAX_SQLITE_INTEGER-1)
    def change():
        projects.manage(actor); e=selected(actor,environment_id,'publish')
        if any(type(x) is not bool for x in (read,write,publish)) or ((write or publish) and not read): raise DomainError('invalid_input','Invalid grant.')
        if not Membership.objects.filter(workspace_id=actor.workspace_id,user_id=user_id,user__is_active=True).exists(): raise DomainError('invalid_input','Member unavailable.')
        if type(revision) is not int or not Environment.objects.filter(pk=e.pk,revision=revision).update(revision=revision+1): raise DomainError('revision_conflict','Environment changed.',status=409)
        SourceGrant.objects.update_or_create(user_id=user_id,source=resolve(ref(e.pk)),defaults=dict(read=read,write=write,publish=publish))
        e.refresh_from_db(); return view(e)
    return atomic_write(change)
