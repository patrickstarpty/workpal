"""Current authorization, normalization and atomic graph publication."""
import copy
import re
from django.db.models import Max
from workpal.contracts import DomainError, ObjectRef
from workpal.access import service as access
from workpal.identity.service import require_member
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from .graph import compile_graph
from .graph_models import GraphDraft, GraphVersion
from .service import manage


def invalid():
    raise DomainError('invalid_input', 'Invalid graph persistence input.')


def integer(value, minimum=1):
    if type(value) is not int or not minimum <= value <= MAX_SQLITE_INTEGER: invalid()
    return value


def ref(pk, version=False):
    return ObjectRef('workflow_graph_version' if version else 'workflow_graph', str(pk))


def inputs(actor, definition, capability='read'):
    from workpal.agents import service as agents
    refs, resolved = [], []
    for node in definition['nodes']:
        if node['type'] != 'agent_task': continue
        config = node['config']
        integer(config['agent_id'])
        agents.read(actor, config['agent_id'])
        refs.append(agents.ref(config['agent_id']))
        values = config['input_refs']
        if len(values) > 50 or len(set(values)) != len(values): invalid()
        parsed = []
        for value in values:
            if len(value) > 256 or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}:[^:]+', value): invalid()
            try: value.encode('utf-8')
            except UnicodeError: invalid()
            kind, identifier = value.split(':', 1)
            item = ObjectRef(kind, identifier)
            access.resolve(item)
            access.authorize(actor, capability, [item])
            refs.append(item)
            parsed.append(dict(kind=kind, id=identifier))
        resolved.append(dict(node_id=node['id'], agent_id=config['agent_id'], input_refs=parsed))
    access.authorize(actor, capability, refs)
    return refs, resolved


def selected(actor, pk, capability='read', version=False):
    integer(pk)
    require_member(actor, actor.workspace_id)
    row = (GraphVersion if version else GraphDraft).objects.filter(pk=pk, workspace_id=actor.workspace_id).first()
    if row is None: raise DomainError('not_found', 'Graph unavailable.', status=404)
    access.authorize(actor, capability, [ref(pk, version)])
    return row


def view(row, metadata=False):
    if isinstance(row, GraphVersion):
        return copy.deepcopy(dict(id=row.pk, draft_id=row.draft_id, number=row.number, name=row.name,
            graph=row.graph, resolved_inputs=row.resolved_inputs, published_by=row.published_by_id,
            published_at=row.published_at.isoformat()))
    data = dict(id=row.pk, name=row.name, revision=row.revision, current_version_id=row.current_version_id or 0)
    if not metadata: data['definition'] = copy.deepcopy(row.definition)
    return data


def normalized(name, definition):
    if type(name) is not str or not name.strip() or len(name)>200: invalid()
    try: name.encode('utf-8')
    except UnicodeError: invalid()
    return compile_graph(definition)


def create(actor, name, definition):
    def write():
        manage(actor)
        graph = normalized(name, definition)
        refs, _ = inputs(actor, graph['definition'])
        row = GraphDraft.objects.create(workspace_id=actor.workspace_id, name=name, definition=graph['definition'])
        access.register_object(actor.workspace_id, ref(row.pk), refs)
        return view(row)
    return atomic_write(write)


def cas(row, revision, **changes):
    integer(revision)
    if revision == MAX_SQLITE_INTEGER: invalid()
    if not GraphDraft.objects.filter(pk=row.pk, revision=revision).update(revision=revision+1, **changes):
        raise DomainError('revision_conflict', 'Graph changed.', status=409)
    row.refresh_from_db()


def update(actor, draft_id, revision, name, definition):
    def write():
        manage(actor)
        row = selected(actor, draft_id, 'write')
        graph = normalized(name, definition)
        refs, _ = inputs(actor, graph['definition'], 'write')
        cas(row, revision, name=name, definition=graph['definition'])
        access.register_object(actor.workspace_id, ref(row.pk), refs)
        return view(row)
    return atomic_write(write)


def publish(actor, draft_id, revision):
    def write():
        manage(actor)
        row = selected(actor, draft_id, 'publish')
        graph = compile_graph(row.definition)
        refs, resolved = inputs(actor, graph['definition'], 'publish')
        cas(row, revision)
        number = (GraphVersion.objects.filter(draft=row).aggregate(n=Max('number'))['n'] or 0)+1
        version = GraphVersion.objects.create(workspace_id=actor.workspace_id, draft=row, number=number,
            name=row.name, graph=graph, resolved_inputs=resolved, published_by_id=actor.user_id)
        access.register_object(actor.workspace_id, ref(version.pk, True), [ref(row.pk), *refs])
        GraphDraft.objects.filter(pk=row.pk, revision=row.revision).update(current_version=version)
        return view(version)
    return atomic_write(write)


def read(actor, draft_id): return view(selected(actor, draft_id))
def read_version(actor, version_id): return view(selected(actor, version_id, version=True))


def list_drafts(actor, cursor=0, limit=50):
    require_member(actor, actor.workspace_id)
    integer(cursor, 0); integer(limit)
    if limit>200: invalid()
    visible=[]
    for row in GraphDraft.objects.filter(workspace_id=actor.workspace_id, pk__gt=cursor).order_by('pk').iterator():
        try: access.authorize(actor, 'read', [ref(row.pk)])
        except DomainError as error:
            if error.status != 403: raise
            continue
        visible.append(view(row, True))
        if len(visible)>limit: break
    return dict(items=visible[:limit], next_cursor=visible[limit-1]['id'] if len(visible)>limit else 0)
