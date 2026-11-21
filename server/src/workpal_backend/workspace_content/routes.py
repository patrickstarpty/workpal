"""Authenticated local workspace content, without execution or integrations."""
from datetime import datetime, timezone
import json
import math
from uuid import uuid4
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from starlette.concurrency import run_in_threadpool

from workpal_backend.auth.dependencies import Principal, require_principal
from workpal_backend.auth.json_codec import user_response
from workpal_backend.auth.service import get_user
from workpal_backend.workspaces import service
from workpal_backend.workspaces.models import issue_status, members, workspaces
from . import repository as repo

router = APIRouter()
COLLECTIONS = ('projects', 'issues', 'agents', 'skills', 'squads', 'autopilots', 'labels')
METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
UNAVAILABLE = 'This operation is unavailable in the local backend.'
ISSUE_DETAILS = {'comments', 'timeline', 'children', 'labels', 'task-runs', 'wakeups',
                 'system-wakeups', 'duplicates', 'pull-requests', 'environments',
                 'subscribers', 'attachments', 'activity', 'tasks', 'runs'}
DETAILS = {
    'issues': ISSUE_DETAILS,
    'projects': {'resources', 'subscription', 'members', 'comments', 'subscribers', 'attachments', 'activity'},
    'squads': {'members/status', 'members', 'activity'},
    'agents': {'tasks', 'runs', 'activity'},
    'skills': {'versions'},
    'autopilots': {'runs'},
}


def execute(request, principal, operation):
    """Resolve explicit canonical workspace and membership before any content access."""
    slug = request.headers.get('x-workspace-slug')
    if not slug or not slug.strip():
        raise HTTPException(400, 'X-Workspace-Slug is required')
    try:
        with request.app.state.database.transaction() as session:
            workspace = repo.resolve_workspace(session, principal, slug)
            if request.method not in ('GET', 'HEAD', 'OPTIONS'):
                # Recheck membership under SQLite's writer serialization so a
                # concurrently revoked member cannot write after the initial read.
                session.execute(update(workspaces).where(workspaces.c.id == workspace['id']).values(
                    issue_counter=workspaces.c.issue_counter))
                service.require_workspace_access(session, principal, workspace['id'])
            return operation(session, workspace)
    except service.WorkspaceAccessError as exc:
        raise HTTPException(404, 'workspace not found') from exc


async def read_body(request):
    raw = await request.body()
    if len(raw) > 1024 * 1024:
        raise HTTPException(413, 'Request too large')
    try:
        body = json.loads(raw or b'{}')
        # The standard decoder permits NaN and overflows such as 1e999. Neither
        # belongs in stored JSON, and invalid Unicode cannot be emitted safely.
        json.dumps(body, allow_nan=False, ensure_ascii=False).encode('utf-8')
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise HTTPException(400, 'Invalid JSON') from exc
    if not isinstance(body, dict):
        raise HTTPException(400, 'Expected an object')
    return body


def required_record(session, workspace_id, kind, record_id):
    row = repo.get_record(session, workspace_id, kind, record_id)
    if row is None:
        raise HTTPException(404, 'Record not found')
    return row


def bounded_integer(value, default, minimum, maximum=None):
    try:
        number = int(float(value))
    except (ValueError, TypeError, OverflowError):
        number = default
    return max(minimum, min(maximum, number) if maximum is not None else number)


def page(rows, params, default=10000, maximum=10000):
    offset = bounded_integer(params.get('offset'), 0, 0)
    limit = bounded_integer(params.get('limit'), default, 1, maximum)
    return rows[offset:offset + limit]


def collection_list(session, workspace, kind, params):
    rows = repo.list_records(session, workspace['id'], kind)
    for field in ('status', 'project_id'):
        if field in params:
            rows = [row for row in rows if row.get(field) == params[field]]
    if 'q' in params:
        query = params['q'].lower()
        rows = [row for row in rows if query in str(row.get('title') or row.get('name') or '').lower()]
    total = len(rows)
    rows = page(rows, params)
    return {kind: rows, 'total': total} if kind in ('projects', 'issues', 'labels') else rows


def validate_references(session, workspace, kind, body):
    """A mutation cannot attach records to entities from another workspace."""
    for field, collection in (('project_id', 'projects'), ('parent_issue_id', 'issues'), ('runtime_id', 'runtimes')):
        if body.get(field) is not None:
            if not isinstance(body[field], str):
                raise HTTPException(400, f'{field} must be text')
            required_record(session, workspace['id'], collection, body[field])
    for prefix in ('assignee', 'lead'):
        identity = body.get(prefix + '_id')
        identity_type = body.get(prefix + '_type')
        if identity is None:
            continue
        if not isinstance(identity, str):
            raise HTTPException(400, f'{prefix}_id must be text')
        if identity_type == 'agent':
            required_record(session, workspace['id'], 'agents', identity)
        elif identity_type == 'member':
            member = session.execute(select(members.c.id).where(
                members.c.workspace_id == workspace['id'],
                (members.c.id == identity) | (members.c.user_id == identity),
            )).first()
            if member is None:
                raise HTTPException(404, 'Member not found')
        elif identity_type == 'squad':
            required_record(session, workspace['id'], 'squads', identity)
        else:
            raise HTTPException(400, f'invalid {prefix}_type')


def save_collection(session, workspace, principal, kind, body, old=None):
    field = 'title' if kind in ('issues', 'projects', 'autopilots') else 'name'
    if old is None or field in body:
        value = body.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 500:
            raise HTTPException(400, f'{field} must contain 1–500 characters')
    for name in ('description', 'status', 'priority'):
        if name in body and body[name] is not None and not isinstance(body[name], str):
            raise HTTPException(400, f'{name} must be text')
    for name in ('labels', 'member_preview'):
        if name in body and not isinstance(body[name], list):
            raise HTTPException(400, f'{name} must be an array')
    if 'position' in body and (isinstance(body['position'], bool) or not isinstance(body['position'], (int, float)) or not math.isfinite(body['position'])):
        raise HTTPException(400, 'position must be a finite number')
    references = {**(old or {}), **body}
    # Validate only relationships supplied by the client, preserving historical data.
    validate_references(session, workspace, kind, {key: references.get(key) for key in
        ('project_id', 'parent_issue_id', 'runtime_id', 'assignee_id', 'assignee_type', 'lead_id', 'lead_type')
        if key in body or (key.endswith('_type') and key.replace('_type', '_id') in body)})
    now = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    record_id = old['id'] if old else str(uuid4())
    defaults = dict(id=record_id, workspace_id=workspace['id'], created_at=now,
                    creator_id=principal.user_id, creator_type='member',
                    status='todo' if kind == 'issues' else 'in_progress', priority='none',
                    icon=None, lead_type=None, lead_id=None, start_date=None, due_date=None,
                    description='', labels=[], metadata={}, properties={},
                    position=len(repo.list_records(session, workspace['id'], kind)), parent_issue_id=None,
                    project_id=None, assignee_type=None, assignee_id=None, visibility='workspace',
                    issue_count=0, done_count=0, sub_issue_count=0, completed_sub_issue_count=0)
    if kind == 'agents':
        defaults.update(owner_id=principal.user_id, status='offline')
    if kind == 'issues' and old is None:
        number = session.scalar(update(workspaces).where(workspaces.c.id == workspace['id']).values(
            issue_counter=workspaces.c.issue_counter + 1).returning(workspaces.c.issue_counter))
        defaults.update(number=number, identifier=f"{workspace['issue_prefix']}-{number}", priority='medium')
    protected = {'id', 'workspace_id', 'created_at', 'updated_at', 'creator_id', 'creator_type',
                 'owner_id', 'owner_type', 'author_id', 'author_type', 'user_id', 'number', 'identifier'}
    changes = {key: value for key, value in body.items() if key not in protected}
    row = {**defaults, **(old or {}), **changes, 'updated_at': now}
    row['id'], row['workspace_id'] = record_id, workspace['id']
    return repo.put_record(session, workspace['id'], kind, row)


def detail(session, workspace, principal, kind, record, operation):
    workspace_id, record_id = workspace['id'], record['id']
    if kind == 'issues':
        if operation in ('comments', 'timeline'):
            comments = sorted((row for row in repo.list_records(session, workspace_id, 'comments')
                               if row.get('issue_id') == record_id), key=lambda row: row.get('created_at') or '')
            if operation == 'comments':
                return comments
            return [{**row, 'type': 'comment', 'comment_type': row.get('type'),
                     'actor_type': row.get('author_type'), 'actor_id': row.get('author_id')} for row in comments]
        if operation == 'children':
            return {'issues': [row for row in repo.list_records(session, workspace_id, 'issues') if row.get('parent_issue_id') == record_id]}
        if operation == 'labels':
            return record.get('labels') or []
        if operation == 'pull-requests':
            return {'pull_requests': [], 'auto_complete': None}
        if operation == 'environments':
            return {'environments': [], 'configs': [], 'pending_starts': [], 'failed_starts': []}
        if operation == 'duplicates':
            return {'duplicate_of': None, 'duplicates': []}
    if kind == 'projects':
        if operation == 'resources':
            return {'resources': [], 'total': 0}
        if operation == 'subscription':
            return {'subscribed': False}
        if operation == 'members':
            return {'members': [], 'total': 0, 'manager_id': principal.user_id}
    if kind == 'squads' and operation in ('members', 'members/status'):
        preview = [row for row in record.get('member_preview', []) if isinstance(row, dict)
                   and isinstance(row.get('member_id'), str) and row.get('member_type') in ('agent', 'member')]
        if operation == 'members/status':
            return {'members': [{'member_type': row['member_type'], 'member_id': row['member_id'],
                                 'status': 'offline' if row['member_type'] == 'agent' else None,
                                 'active_issues': [], 'last_active_at': None} for row in preview]}
        return [{**row, 'id': f"{record_id}:{row['member_type']}:{row['member_id']}",
                 'squad_id': record_id, 'created_at': record.get('created_at')} for row in preview]
    return []


def collection_endpoint(kind):
    async def endpoint(request: Request, principal: Principal = Depends(require_principal)):
        body = await read_body(request) if request.method in ('POST', 'PUT', 'PATCH') else {}
        def operation(session, workspace):
            if request.method == 'GET':
                return collection_list(session, workspace, kind, request.query_params)
            if request.method == 'POST':
                return JSONResponse(save_collection(session, workspace, principal, kind, body), status_code=201)
            raise HTTPException(501, UNAVAILABLE)
        return await run_in_threadpool(execute, request, principal, operation)
    return endpoint


def record_endpoint(kind):
    async def endpoint(record_path: str, request: Request, principal: Principal = Depends(require_principal)):
        body = await read_body(request) if request.method in ('POST', 'PUT', 'PATCH') else {}
        def operation(session, workspace):
            # A path converter preserves imported IDs containing spaces or slashes.
            row = repo.get_record(session, workspace['id'], kind, record_path)
            if row is not None:
                if request.method == 'GET':
                    return row
                if request.method in ('PUT', 'PATCH') and kind in COLLECTIONS:
                    return save_collection(session, workspace, principal, kind, body, row)
                if request.method == 'DELETE' and kind in COLLECTIONS:
                    repo.delete_record(session, workspace['id'], kind, record_path)
                    return {}
                raise HTTPException(501, UNAVAILABLE)
            for suffix in sorted(DETAILS.get(kind, ()), key=len, reverse=True):
                if record_path.endswith('/' + suffix):
                    record_id = record_path[:-len(suffix) - 1]
                    row = required_record(session, workspace['id'], kind, record_id)
                    if request.method == 'GET':
                        return detail(session, workspace, principal, kind, row, suffix)
                    raise HTTPException(501, UNAVAILABLE)
            if request.method == 'POST':
                raise HTTPException(501, UNAVAILABLE)
            raise HTTPException(404, 'Record not found')
        return await run_in_threadpool(execute, request, principal, operation)
    return endpoint


@router.get('/api/bootstrap')
def bootstrap(request: Request, principal: Principal = Depends(require_principal)):
    return execute(request, principal, lambda session, workspace: user_response({
        'workspace': service.response(workspace), 'user': get_user(session, principal.user_id),
        'projects': repo.list_records(session, workspace['id'], 'projects'),
    }))


def search_endpoint(kind):
    def endpoint(request: Request, principal: Principal = Depends(require_principal)):
        def operation(session, workspace):
            query = request.query_params.get('q', '').lower()
            rows = [row for row in repo.list_records(session, workspace['id'], kind)
                    if any(isinstance(row.get(field), str) and query in row[field].lower()
                           for field in ('title', 'identifier', 'description'))]
            return {kind: [{**row, 'match_source': 'title'} for row in page(rows, request.query_params, 20, 100)]}
        return execute(request, principal, operation)
    return endpoint


for _kind in ('issues', 'projects'):
    router.add_api_route(f'/api/{_kind}/search', search_endpoint(_kind), methods=['GET'])


@router.get('/api/issues/child-progress')
def child_progress(request: Request, principal: Principal = Depends(require_principal)):
    def operation(session, workspace):
        issues = repo.list_records(session, workspace['id'], 'issues')
        progress = []
        for row in issues:
            children = [child for child in issues if child.get('parent_issue_id') == row['id']]
            if children:
                progress.append({'parent_issue_id': row['id'], 'total': len(children),
                                 'done': sum(child.get('status') == 'done' for child in children)})
        return {'progress': progress}
    return execute(request, principal, operation)


@router.api_route('/api/issues/table/{operation}', methods=['GET', 'POST'])
async def issue_table(operation: str, request: Request, principal: Principal = Depends(require_principal)):
    body = await read_body(request)
    def query_rows(session, workspace):
        if operation not in ('rows', 'groups', 'facets'):
            raise HTTPException(501, UNAVAILABLE)
        query = body.get('query') or {}
        if not isinstance(query, dict) or not isinstance(query.get('scope', {}), dict) or not isinstance(query.get('filters', {}), dict):
            raise HTTPException(400, 'invalid issue query')
        rows = repo.list_records(session, workspace['id'], 'issues')
        project_id = query.get('scope', {}).get('project_id')
        if project_id:
            rows = [row for row in rows if row.get('project_id') == project_id]
        search = query.get('search')
        if search:
            if not isinstance(search, str):
                raise HTTPException(400, 'search must be text')
            rows = [row for row in rows if search.lower() in f"{row.get('title', '')} {row.get('identifier', '')}".lower()]
        for key, field in (('statuses', 'status'), ('priorities', 'priority'), ('project_ids', 'project_id')):
            values = query.get('filters', {}).get(key)
            if values is not None and not isinstance(values, list):
                raise HTTPException(400, 'filters must be arrays')
            if values:
                rows = [row for row in rows if row.get(field) in values]
        key = body.get('group_key')
        if key:
            rows = [row for row in rows if key in (row.get('status'), 'status:' + str(row.get('status')), 'status/' + str(row.get('status')))]
        hierarchy = body.get('hierarchy') or {}
        if not isinstance(hierarchy, dict):
            raise HTTPException(400, 'invalid hierarchy')
        if hierarchy.get('enabled'):
            rows = [row for row in rows if row.get('parent_issue_id') == (body.get('parent_id') or None)]
        common = {'query_fingerprint': 'local', 'total': len(rows), 'next_cursor': None}
        if operation == 'rows':
            return {**common, 'group_key': key or None, 'parent_id': body.get('parent_id') or None,
                    'branch_total': len(rows), 'rows': [{'issue': row, 'direct_child_count': row.get('sub_issue_count') or 0} for row in rows]}
        if operation == 'groups':
            statuses = list(dict.fromkeys(row.get('status') for row in rows))
            return {**common, 'groups': [{'key': 'status:' + str(status), 'value': {'kind': 'status', 'status': status},
                                         'count': sum(row.get('status') == status for row in rows)} for status in statuses]}
        return {**common, 'facets': []}
    return await run_in_threadpool(execute, request, principal, query_rows)


@router.get('/api/issue-statuses')
def statuses(request: Request, principal: Principal = Depends(require_principal)):
    def operation(session, workspace):
        rows = [dict(row) for row in session.execute(select(issue_status).where(
            issue_status.c.workspace_id == workspace['id'], issue_status.c.archived_at.is_(None),
        ).order_by(issue_status.c.position, issue_status.c.created_at, issue_status.c.key)).mappings()]
        return {'statuses': rows, 'categories': ['unstarted', 'started', 'done', 'closed'], 'total': len(rows)}
    return execute(request, principal, operation)


@router.api_route('/api/issue-view-preferences', methods=METHODS)
@router.api_route('/api/notification-preferences', methods=METHODS)
async def preferences(request: Request, principal: Principal = Depends(require_principal)):
    body = await read_body(request) if request.method in ('PUT', 'PATCH') else {}
    def operation(session, workspace):
        if request.method not in ('GET', 'PUT', 'PATCH'):
            raise HTTPException(501, UNAVAILABLE)
        params = dict(request.query_params)
        if request.method != 'GET' and body.get('scope_type'):
            params = {key: body[key] for key in ('scope_type', 'scope_id') if body.get(key) is not None}
        query = urlencode(sorted(params.items()))
        legacy_id = request.url.path + ('?' + query if query else '')
        record_id = principal.user_id + ':' + legacy_id
        if request.method == 'GET':
            row = repo.get_record(session, workspace['id'], 'preferences', record_id)
            if row is None:
                # Imported preferences predate personal ownership. They only belong to
                # their migrated creator, never to a new member in the same workspace.
                imported = repo.get_record(session, workspace['id'], 'preferences', legacy_id)
                if imported and imported.get('user_id') == principal.user_id:
                    row = imported
            return row.get('value', {}) if row else {}
        value = {key: val for key, val in body.items() if key not in ('id', 'user_id', 'workspace_id', 'owner_id')}
        repo.put_record(session, workspace['id'], 'preferences', {
            'id': record_id, 'user_id': principal.user_id, 'workspace_id': workspace['id'], 'value': value,
        })
        return value
    return await run_in_threadpool(execute, request, principal, operation)


def known_read_endpoint(value=None, collection=None):
    def endpoint(request: Request, principal: Principal = Depends(require_principal)):
        def operation(session, workspace):
            if request.method != 'GET':
                raise HTTPException(501, UNAVAILABLE)
            return repo.list_records(session, workspace['id'], collection) if collection else value
        return execute(request, principal, operation)
    return endpoint


for _path, _value in {
    '/api/issues/unread': [], '/api/chat/pending-tasks': {'tasks': []},
    '/api/chat/pending-tasks/has-any': {'has_pending': False}, '/api/agent-task-snapshot': [],
    '/api/issue-wakeup-summaries': [], '/api/issue-wakeup-paused': [],
    '/api/issue-workflows': {'workflows': [], 'total': 0}, '/api/agent-run-counts': [],
    '/api/inbox/unread-summary': {}, '/api/inbox': [], '/api/pins': [],
    '/api/issue-views': [], '/api/notifications': [], '/api/connected-apps': [],
}.items():
    router.add_api_route(_path, known_read_endpoint(_value), methods=METHODS)

router.add_api_route('/api/runtimes', known_read_endpoint(collection='runtimes'), methods=METHODS)
router.add_api_route('/api/runtimes/{record_path:path}', record_endpoint('runtimes'), methods=METHODS)
router.add_api_route('/api/chat/sessions', known_read_endpoint(collection='sessions'), methods=METHODS)
router.add_api_route('/api/chat/sessions/{record_path:path}', record_endpoint('sessions'), methods=METHODS)

for _kind in COLLECTIONS:
    router.add_api_route(f'/api/{_kind}', collection_endpoint(_kind), methods=METHODS)
    router.add_api_route(f'/api/{_kind}/{{record_path:path}}', record_endpoint(_kind), methods=METHODS)
