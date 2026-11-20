"""Immutable initialization facts through the Registry Interface; no execution."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import re
from workpal.contracts import SubjectRef, ObjectRef, ActionRequest, DomainError
from workpal.access import service as access
from workpal.work import issues
from workpal.execution.admission import admit_initialization
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from . import persistence as p
from .graph_models import GraphInstance


def subject_id(subject):
    if not isinstance(subject,SubjectRef): p.invalid()
    if subject.type != 'issue':
        raise DomainError('unsupported_subject','Unsupported subject.')
    if type(subject.id) is not str or not re.fullmatch(r'[1-9][0-9]*',subject.id) or len(subject.id)>19: p.invalid()
    value=int(subject.id)
    if value>=MAX_SQLITE_INTEGER: p.invalid()
    return value


def ref(pk): return ObjectRef('workflow_graph_instance',str(pk))


def resolve(actor,subject,version_id):
    row=issues.selected(actor,subject_id(subject),'write')
    p.integer(version_id)
    version=p.read_version(actor,version_id)
    refs=[issues.ref(row.pk),ObjectRef('project',str(row.project_id)),p.ref(version_id,True)]
    agents={}
    for node in version['resolved_inputs']:
        aid=node['agent_id']
        admission=admit_initialization(actor,aid)
        agents[aid]=admission.agent
        refs.extend([ObjectRef('agent',str(aid)),*admission.source_refs])
        refs.extend(ObjectRef(**value) for value in node['input_refs'])
    access.authorize(actor,'read',refs)
    return version,refs,[agents[key] for key in sorted(agents)]


def view(row):
    return deepcopy(dict(id=row.pk,version_id=row.version_id,subject=dict(type='issue',id=str(row.issue_id)),state=row.state,snapshot=row.snapshot,sha256=row.sha256,created_at=row.created_at.isoformat()))


def initialize(actor,subject,version_id,key):
    subject_id(subject); p.integer(version_id)
    from workpal.actions.registry import execute
    return deepcopy(execute(actor,ActionRequest('workflow_graph.instance.initialize',dict(subject=asdict(subject),version_id=version_id),None,key)).data)


def create_record(actor,subject,version_id):
    def write():
        version,refs,agents=resolve(actor,subject,version_id)
        issue=issues.read(actor,subject_id(subject))
        requirements=issues.read_requirements(actor,issue['id'],issue['requirements_revision'])
        refs.append(issues.requirement_ref(requirements['id']))
        refs=set(refs)
        refs.update(access.derive_scope(refs).source_refs)
        refs=sorted(refs,key=lambda value:(value.kind,value.id))
        access.authorize(actor,'read',refs)
        snapshot=deepcopy(dict(schema_version=1,graph_version=version,issue=issue,requirements=requirements,agents=agents,source_refs=[asdict(value) for value in refs],created_by=actor.user_id))
        digest=hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf8')).hexdigest()
        row=GraphInstance.objects.create(workspace_id=actor.workspace_id,version_id=version_id,issue_id=issue['id'],requirements_id=requirements['id'],created_by_id=actor.user_id,snapshot=snapshot,sha256=digest)
        access.register_object(actor.workspace_id,ref(row.pk),refs)
        return view(row)
    return atomic_write(write)


def selected(actor,instance_id):
    p.integer(instance_id)
    row=GraphInstance.objects.filter(pk=instance_id,workspace_id=actor.workspace_id).select_related('requirements','issue','version').first()
    if row is None: raise DomainError('not_found','Instance unavailable.',status=404)
    access.authorize(actor,'read',[ref(row.pk)])
    s=row.snapshot
    if (row.issue.workspace_id!=actor.workspace_id or row.version.workspace_id!=actor.workspace_id or row.requirements.issue_id!=row.issue_id or s['issue']['id']!=row.issue_id or s['requirements']['id']!=row.requirements_id or s['graph_version']['id']!=row.version_id or s['created_by']!=row.created_by_id): p.invalid()
    access.authorize(actor,'read',[ObjectRef(**value) for value in s['source_refs']])
    historical=issues.read_requirements(actor,row.issue_id,row.requirements.number)
    if historical!=s['requirements']: p.invalid()
    return row


def read(actor,instance_id): return view(selected(actor,instance_id))


def summary(row):
    return deepcopy({key: value for key, value in view(row).items() if key != 'snapshot'})


def list_instances(actor, cursor=0, limit=50):
    from workpal.identity.service import require_member
    require_member(actor, actor.workspace_id)
    if type(cursor) is not int or not 0 <= cursor < MAX_SQLITE_INTEGER:
        p.invalid()
    if type(limit) is not int or not 1 <= limit <= 200:
        p.invalid()
    items = []
    for pk in GraphInstance.objects.filter(workspace_id=actor.workspace_id, pk__gt=cursor).order_by('pk').values_list('pk', flat=True).iterator():
        try:
            row = selected(actor, pk)
        except DomainError as error:
            if error.status == 403:
                continue
            raise
        if len(items) == limit:
            return dict(items=items, next_cursor=items[-1]['id'])
        items.append(summary(row))
    return dict(items=items, next_cursor=0)
