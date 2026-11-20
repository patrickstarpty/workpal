"""Unverified repository configuration; provenance is append-only."""
import unicodedata
from urllib.parse import urlsplit
from django.utils import timezone
from workpal.contracts import DomainError, ObjectRef
from workpal.access.service import authorize, register_object
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from . import service
from .models import ProjectResource

FIELDS = {'label':200, 'provider':20, 'repository_ref':2000, 'checkout_ref':500}
def ref(pk): return ObjectRef('project_resource',str(pk))
def fail(): raise DomainError('invalid_input','Invalid resource fields.')
def sources(values):
    if type(values) is not list or len(values)>50: fail()
    for v in values:
        if type(v) is not dict or set(v)!={'kind','id'} or any(type(x) is not str or not x for x in v.values()): fail()
    return [ObjectRef(**v) for v in values]
def validate(changes):
    if set(changes)-set(FIELDS): fail()
    for k,v in changes.items():
        if type(v) is not str or len(v)>FIELDS[k] or (k!='checkout_ref' and not v.strip()): fail()
        if any(unicodedata.category(c).startswith('C') for c in v): fail()
    if 'provider' in changes and changes['provider'] not in ('github','azure_repos'): fail()
    if 'repository_ref' in changes:
        value=changes['repository_ref']
        try:
            u=urlsplit(value)
            if u.username is not None or u.password is not None or u.query or u.fragment or '@' in value: fail()
            if u.scheme and (u.scheme!='https' or not u.netloc): fail()
        except ValueError: fail()
def view(r):
    return {k:(getattr(r,k).isoformat() if k.endswith('_at') else getattr(r,k)) for k in ('id','project_id','label','provider','repository_ref','checkout_ref','verification_status','archived','revision','created_at','updated_at')}
def selected(actor, project_id, resource_id, capability='read'):
    service.selected(actor,project_id,capability)
    r=ProjectResource.objects.filter(pk=resource_id,project_id=project_id,workspace_id=actor.workspace_id).first()
    if r is None: raise DomainError('not_found','Resource unavailable.',status=404)
    authorize(actor,capability,[ref(r.pk)])
    return r
def create(actor, project_id, label, provider, repository_ref, checkout_ref='', source_refs=None):
    def write():
        service.manage(actor)
        p=service.selected(actor,project_id,'write')
        if p.archived: raise DomainError('project_archived','Project archived.',status=409)
        changes=dict(label=label,provider=provider,repository_ref=repository_ref,checkout_ref=checkout_ref)
        validate(changes)
        refs=sources([] if source_refs is None else source_refs)
        authorize(actor,'write',refs)
        r=ProjectResource.objects.create(workspace_id=actor.workspace_id,project=p,**changes)
        register_object(actor.workspace_id,ref(r.pk),[service.ref(p.pk),*refs])
        return view(r)
    return atomic_write(write)
def read(actor,project_id,resource_id): return view(selected(actor,project_id,resource_id))
def update(actor,project_id,resource_id,revision,source_refs=None,**changes):
    def write():
        service.manage(actor)
        validate(changes)
        if type(revision) is not int or not 1<=revision<MAX_SQLITE_INTEGER: fail()
        r=selected(actor,project_id,resource_id,'write')
        refs=sources([] if source_refs is None else source_refs)
        authorize(actor,'write',refs)
        if not ProjectResource.objects.filter(pk=r.pk,revision=revision).update(**changes,revision=revision+1,verification_status='unverified',updated_at=timezone.now()):
            raise DomainError('revision_conflict','Resource changed.',status=409)
        register_object(actor.workspace_id,ref(r.pk),refs)
        r.refresh_from_db(); return view(r)
    return atomic_write(write)
def set_archived(actor,project_id,resource_id,revision,archived):
    def write():
        service.manage(actor)
        if type(revision) is not int or not 1<=revision<MAX_SQLITE_INTEGER: fail()
        r=selected(actor,project_id,resource_id,'write')
        if not ProjectResource.objects.filter(pk=r.pk,revision=revision).update(archived=archived,revision=revision+1,updated_at=timezone.now()):
            raise DomainError('revision_conflict','Resource changed.',status=409)
        r.refresh_from_db(); return view(r)
    return atomic_write(write)
def list_resources(actor,project_id,include_archived=False,cursor=0,limit=50):
    service.selected(actor,project_id)
    if type(limit) is not int or not 1<=limit<=200 or type(cursor) is not int or cursor<0: fail()
    rows=ProjectResource.objects.filter(workspace_id=actor.workspace_id,project_id=project_id,pk__gt=cursor).order_by('pk')
    if not include_archived: rows=rows.filter(archived=False)
    visible=[]
    for r in rows.iterator():
        try: authorize(actor,'read',[ref(r.pk)])
        except DomainError as e:
            if e.status!=403: raise
            continue
        visible.append(view(r))
        if len(visible)>limit: break
    return dict(items=visible[:limit],next_cursor=visible[limit-1]['id'] if len(visible)>limit else 0)
