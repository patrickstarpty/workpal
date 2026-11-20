"""Project records with current authorization and visible pagination."""
from dataclasses import asdict
from django.utils import timezone
from workpal.contracts import DomainError, ObjectRef
from workpal.identity.service import require_member
from workpal.access.service import authorize, register_object
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from .models import Project
from .contracts import ProjectView

def ref(project_id):
    return ObjectRef('project', str(project_id))

def selected(actor, project_id, capability='read'):
    require_member(actor, actor.workspace_id)
    p = Project.objects.filter(workspace_id=actor.workspace_id, pk=project_id).first()
    if p is None:
        raise DomainError('not_found', 'Project unavailable.', status=404)
    authorize(actor, capability, [ref(p.pk)])
    return p

def view(p):
    return asdict(ProjectView(p.pk, p.name, p.description, p.archived, p.revision,
                              p.created_at.isoformat(), p.updated_at.isoformat(), p.workflow_version_id or 0))

def manage(actor):
    if require_member(actor, actor.workspace_id).role not in ('owner', 'admin'):
        raise DomainError('permission_denied', 'Permission denied.', status=403)

def validate_changes(changes):
    # Workspace identity, revision and timestamps are owned by this module.
    if not changes or set(changes) - {'name', 'description', 'archived'}:
        raise DomainError('invalid_input', 'Invalid project fields.')
    for field, maximum in (('name', 200), ('description', 10000)):
        if field in changes and (type(changes[field]) is not str or len(changes[field]) > maximum
                                 or (field == 'name' and not changes[field].strip())):
            raise DomainError('invalid_input', 'Invalid project fields.')
    if 'archived' in changes and type(changes['archived']) is not bool:
        raise DomainError('invalid_input', 'Invalid project fields.')

def create(actor, name, description=''):
    def write():
        manage(actor)
        validate_changes(dict(name=name, description=description))
        p = Project.objects.create(workspace_id=actor.workspace_id, name=name, description=description)
        register_object(actor.workspace_id, ref(p.pk))
        return view(p)
    return atomic_write(write)

def read(actor, project_id):
    return view(selected(actor, project_id))

def update(actor, project_id, revision, **changes):
    def write():
        manage(actor)
        validate_changes(changes)
        if type(revision) is not int or not 1 <= revision <= MAX_SQLITE_INTEGER:
            raise DomainError('invalid_input', 'Invalid project revision.')
        p = selected(actor, project_id, 'write')
        if not Project.objects.filter(pk=p.pk, workspace_id=actor.workspace_id, revision=revision).update(
                **changes, revision=revision + 1, updated_at=timezone.now()):
            raise DomainError('revision_conflict', 'Project changed.', status=409)
        p.refresh_from_db()
        return view(p)
    return atomic_write(write)

def list_projects(actor, query='', include_archived=False, cursor=0, limit=50):
    require_member(actor, actor.workspace_id)
    rows = Project.objects.filter(workspace_id=actor.workspace_id, pk__gt=cursor).order_by('pk')
    if not include_archived:
        rows = rows.filter(archived=False)
    if query:
        rows = rows.filter(name__icontains=query)
    visible = []
    for p in rows.iterator():
        try:
            authorize(actor, 'read', [ref(p.pk)])
        except DomainError as error:
            if error.status != 403:
                raise
            continue
        visible.append(view(p))
        if len(visible) > limit:
            break
    return dict(items=visible[:limit], next_cursor=visible[limit-1]['id'] if len(visible)>limit else 0)

def workflow_refs(actor, project_id, workflow_version_id=None, capability='read'):
    from workpal.workflows import service as workflows
    p = selected(actor, project_id, capability)
    version_id = p.workflow_version_id if workflow_version_id is None else workflow_version_id
    refs = [ref(p.pk)]
    if version_id:
        workflows.read_version(actor, version_id)
        refs.append(workflows.ref(version_id, True))
    authorize(actor, capability, refs)
    return refs

def set_workflow(actor, project_id, workflow_version_id, revision):
    def write():
        manage(actor)
        if type(workflow_version_id) is not int or not 0 <= workflow_version_id <= MAX_SQLITE_INTEGER:
            raise DomainError('invalid_input', 'Invalid workflow version.')
        if type(revision) is not int or not 1 <= revision < MAX_SQLITE_INTEGER:
            raise DomainError('invalid_input', 'Invalid revision.')
        refs = workflow_refs(actor, project_id, workflow_version_id, 'write')
        if not Project.objects.filter(pk=project_id, workspace_id=actor.workspace_id, revision=revision).update(
                workflow_version_id=workflow_version_id or None, revision=revision+1, updated_at=timezone.now()):
            raise DomainError('revision_conflict', 'Project changed.', status=409)
        register_object(actor.workspace_id, ref(project_id), refs[1:])
        return read(actor, project_id)
    return atomic_write(write)

def snapshot_workflow(actor, project_id):
    from workpal.workflows import service as workflows
    p = selected(actor, project_id)
    workflow_refs(actor, project_id)
    if p.workflow_version_id:
        data = workflows.read_version(actor, p.workflow_version_id)
        return dict(origin='published', version_id=data['id'], name=data['name'],
                    sha256=data['sha256'], definition=data['definition'])
    return workflows.builtin_snapshot()
