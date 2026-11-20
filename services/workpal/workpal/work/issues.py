"""Issue ownership, append-only requirements and current provenance authorization."""
from copy import deepcopy
import hashlib
import json
import re
from django.utils import timezone
from workpal.contracts import Actor, DomainError, ObjectRef
from workpal.identity.service import require_member
from workpal.access.service import authorize, register_object, derive_scope
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from . import service as projects
from .resources import sources
from .models import Issue, IssueRequirements

def fail(): raise DomainError('invalid_input','Invalid issue fields.')
def integer(value, zero=False):
    if type(value) is not int or not (0 if zero else 1)<=value<MAX_SQLITE_INTEGER: fail()
def validate_text(value, maximum, required=False):
    if type(value) is not str or len(value)>maximum or (required and not value.strip()): fail()
    try:
        value.encode('utf-8')
    except UnicodeError:
        fail()
def ref(pk): return ObjectRef('issue',str(pk))
def requirement_ref(pk): return ObjectRef('issue_requirements',str(pk))
def selected(actor, issue_id, capability='read'):
    integer(issue_id)
    require_member(actor,actor.workspace_id)
    row=Issue.objects.filter(pk=issue_id,workspace_id=actor.workspace_id).select_related('current_requirements').first()
    if row is None: raise DomainError('not_found','Issue unavailable.',status=404)
    authorize(actor,capability,[ref(row.pk)])
    return row

def validate(values):
    if not values or set(values)-{'title','description','criteria','assignee_user_id','source_refs'}: fail()
    for key,maximum in [('title',300),('description',20000)]:
        if key in values: validate_text(values[key],maximum,key=='title')
    if 'assignee_user_id' in values: integer(values['assignee_user_id'],True)
    if 'source_refs' in values: sources(values['source_refs'])
    if 'criteria' in values:
        criteria=values['criteria']
        if type(criteria) is not list or len(criteria)>100: fail()
        keys=set()
        for item in criteria:
            if type(item) is not dict or set(item)!={'key','text'}: fail()
            k,t=item['key'],item['text']
            if type(k) is not str or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}',k) or k in keys: fail()
            validate_text(t,2000,True)
            keys.add(k)

def content(row): return deepcopy(dict(title=row.title,description=row.description,criteria=row.criteria))
def append(actor,row,values,number):
    digest=hashlib.sha256(json.dumps(values,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf8')).hexdigest()
    req=IssueRequirements.objects.create(issue=row,number=number,created_by_id=actor.user_id,sha256=digest,**values)
    register_object(actor.workspace_id,requirement_ref(req.pk),[ref(row.pk)])
    row.current_requirements=req
    row.save(update_fields=['current_requirements'])

def assignee(actor,row,user_id):
    if user_id:
        target=Actor(user_id,actor.workspace_id)
        require_member(target,actor.workspace_id)
        authorize(target,'read',[ref(row.pk)])

def view(row, actor):
    authorize(actor, "read", [ref(row.pk), requirement_ref(row.current_requirements_id)])
    from .transitions import category
    cat=category(row)
    return dict(status_category=cat,lifecycle={"backlog":"unstarted","todo":"unstarted","in_progress":"started","in_review":"started","blocked":"started","done":"done","cancelled":"closed"}[cat],blocked_reason=row.blocked_reason,blocked_owner_user_id=row.blocked_owner_id or 0,id=row.pk,parent_issue_id=row.parent_id or 0,project_id=row.project_id,**content(row.current_requirements),assignee_user_id=row.assignee_id or 0,status_key=row.status_key,archived=row.archived,revision=row.revision,requirements_version_id=row.current_requirements_id,requirements_revision=row.current_requirements.number,workflow_snapshot=deepcopy(row.workflow_snapshot),created_at=row.created_at.isoformat(),updated_at=row.updated_at.isoformat())

def create(actor,project_id,title,description='',criteria=None,assignee_user_id=0,source_refs=None,parent_issue_id=0):
    def write():
        integer(project_id)
        from .hierarchy import parent_for_write
        parent=parent_for_write(actor,parent_issue_id)
        values=dict(title=title,description=description,criteria=[] if criteria is None else criteria)
        validate(dict(**values,assignee_user_id=assignee_user_id))
        p=projects.selected(actor,project_id,'write')
        if p.archived: raise DomainError('project_archived','Project archived.',status=409)
        snapshot=projects.snapshot_workflow(actor,p.pk)
        refs=projects.workflow_refs(actor,p.pk)+sources([] if source_refs is None else source_refs)
        if parent: refs.append(ref(parent.pk))
        authorize(actor,'write',refs)
        state=next((s['key'] for s in snapshot['definition']['states'] if s['category']=='backlog'),'backlog')
        row=Issue.objects.create(workspace_id=actor.workspace_id,project=p,parent=parent,created_by_id=actor.user_id,assignee_id=assignee_user_id or None,status_key=state,workflow_snapshot=deepcopy(snapshot))
        register_object(actor.workspace_id,ref(row.pk),refs)
        assignee(actor,row,assignee_user_id)
        append(actor,row,values,1)
        if assignee_user_id:
            authorize(Actor(assignee_user_id, actor.workspace_id), "read", [requirement_ref(row.current_requirements_id)])
        if assignee_user_id:
            from workpal.collaboration.service import notify_assignment
            notify_assignment(actor,row.pk,row.revision)
        return view(row, actor)
    return atomic_write(write)

def read(actor,issue_id): return view(selected(actor,issue_id), actor)
def update(actor,issue_id,revision,**changes):
    def write():
        integer(revision); validate(changes)
        row=selected(actor,issue_id,'write')
        refs=sources(changes.get('source_refs',[])); authorize(actor,'write',refs)
        if not Issue.objects.filter(pk=row.pk,revision=revision).update(revision=revision+1,updated_at=timezone.now()):
            raise DomainError('revision_conflict','Issue changed.',status=409)
        register_object(actor.workspace_id,ref(row.pk),refs)
        previous_assignee=row.assignee_id or 0
        target=changes.get('assignee_user_id',previous_assignee)
        assignee(actor,row,target)
        row.assignee_id=target or None; row.save(update_fields=['assignee'])
        if {"title", "description", "criteria"} & changes.keys():
            previous = requirement_ref(row.current_requirements_id)
            authorize(actor, "read", [previous])
            authorize(actor, "write", [previous])
            register_object(actor.workspace_id, ref(row.pk), derive_scope([previous]).source_refs)
        values=content(row.current_requirements)
        values.update({k:v for k,v in changes.items() if k in values})
        if values!=content(row.current_requirements): append(actor,row,values,row.current_requirements.number+1)
        row.refresh_from_db()
        if target:
            authorize(Actor(target, actor.workspace_id), "read", [requirement_ref(row.current_requirements_id)])
        if target and target != previous_assignee:
            from workpal.collaboration.service import notify_assignment
            notify_assignment(actor,row.pk,row.revision)
        return view(row, actor)
    return atomic_write(write)

def set_archived(actor,issue_id,revision,archived):
    def write():
        integer(revision); row=selected(actor,issue_id,'write')
        if not Issue.objects.filter(pk=row.pk,revision=revision).update(archived=archived,revision=revision+1,updated_at=timezone.now()):
            raise DomainError('revision_conflict','Issue changed.',status=409)
        row.refresh_from_db(); return view(row, actor)
    return atomic_write(write)
def archive(actor,issue_id,revision): return set_archived(actor,issue_id,revision,True)
def restore(actor,issue_id,revision): return set_archived(actor,issue_id,revision,False)
def read_requirements(actor,issue_id,number):
    row=selected(actor,issue_id); integer(number)
    req=IssueRequirements.objects.filter(issue=row,number=number).first()
    if req is None: raise DomainError('not_found','Requirements unavailable.',status=404)
    authorize(actor,'read',[requirement_ref(req.pk)])
    return dict(id=req.pk,issue_id=row.pk,number=req.number,**content(req),sha256=req.sha256,created_by=req.created_by_id,created_at=req.created_at.isoformat())
def list_issues(actor,project_id=None,query='',include_archived=False,cursor=0,limit=50,status_key=None,assignee_user_id=None,parent_issue_id=None):
    require_member(actor,actor.workspace_id); integer(cursor,True); integer(limit)
    if limit>200 or type(query) is not str or len(query)>300 or type(include_archived) is not bool: fail()
    rows=Issue.objects.filter(workspace_id=actor.workspace_id,pk__gt=cursor).order_by('pk')
    if parent_issue_id is not None:
        integer(parent_issue_id,True)
        if parent_issue_id: selected(actor,parent_issue_id)
        rows=rows.filter(parent_id=parent_issue_id or None)
    if project_id is not None: integer(project_id); rows=rows.filter(project_id=project_id)
    if status_key is not None: validate_text(status_key,64,True); rows=rows.filter(status_key=status_key)
    if assignee_user_id is not None: integer(assignee_user_id,True); rows=rows.filter(assignee_id=assignee_user_id or None)
    if not include_archived: rows=rows.filter(archived=False)
    if query: rows=rows.filter(current_requirements__title__icontains=query)
    visible=[]
    for row in rows:
        try: authorize(actor,'read',[ref(row.pk), requirement_ref(row.current_requirements_id)])
        except DomainError as e:
            if e.status!=403: raise
            continue
        data=view(row, actor); data.pop('workflow_snapshot'); visible.append(data)
        if len(visible)>limit: break
    return dict(items=visible[:limit],next_cursor=visible[limit-1]['id'] if len(visible)>limit else 0)


def result_refs(actor, result):
    """Resolve the exact saved content version, including pre-upgrade cache rows."""
    data = result.data
    def unavailable():
        raise DomainError("permission_denied", "Requirements unavailable.", status=403)

    if type(data) is not dict:
        unavailable()
    paged = "items" in data
    if paged and (set(data) != {"items", "next_cursor"} or type(data["items"]) is not list):
        unavailable()
    items = data["items"] if paged else [data]
    refs = []
    for item in items:
        if type(item) is not dict or not {"title", "description", "criteria"} <= item.keys():
            unavailable()
        historical = "issue_id" in item
        issue_id = item.get("issue_id") if historical else item.get("id")
        version_id = item.get("id") if historical else item.get("requirements_version_id")
        number = item.get("number") if historical else item.get("requirements_revision")
        if any(type(value) is not int or not 1 <= value < MAX_SQLITE_INTEGER for value in (issue_id, version_id, number)):
            unavailable()
        subject = ref(issue_id)
        if subject not in result.object_refs or (not paged and result.object_refs[0] != subject):
            unavailable()
        requirement = IssueRequirements.objects.filter(
            pk=version_id, issue_id=issue_id, issue__workspace_id=actor.workspace_id, number=number
        ).first()
        if requirement is None or any(item[key] != getattr(requirement, key) for key in ("title", "description", "criteria")):
            unavailable()
        refs.extend([ref(issue_id), requirement_ref(version_id)])
    return refs
