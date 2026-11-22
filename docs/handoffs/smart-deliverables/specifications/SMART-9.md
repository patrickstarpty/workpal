# Ticket relationship implementation inspection and review
Revision 1. Prepared by Codex during the current evidence audit. This report reviews the inspected checkout; it does not attribute current uncommitted changes to the historical SMART-9 Run.

## Actual source and comparison
The attached diff is `git diff HEAD -- server/src/workpal_backend/workspace_content/routes.py`, captured during this audit. Base HEAD is b93ed96078c90605230b81fdbf240f65f1c93437. It includes other uncommitted workspace-content changes and is explicitly not a clean SMART-9 feature patch. No original task-specific implementation commit has been established. Full inspected source is included to permit review of the boundary logic as it existed at capture time.

## Review findings
R9-01: `required_record` looks up a record in the resolved workspace; `validate_references` checks supplied project and parent references through that workspace. The targeted cross-workspace test rejects foreign references and foreign issue reads/mutations. This supports a narrow server isolation claim.
R9-02: The inspected handler validates parent/project references. That is not evidence of a complete arbitrary related-ticket relationship picker, persisted relationship model, keyboard navigation or return-focus behavior. The historical navigation-complete claim is not established.
R9-03: Current working-tree diff contains assignment/activity and evidence changes beyond this ticket. It must not be accepted as the original SMART-9 change set without a scoped commit or approved patch identifying intended behavior.

## Corrections and recheck
No product behavior was changed in this audit to manufacture a matching diff. R9-01 was rechecked by the actual test named below. R9-02 and R9-03 remain open. No peer code-review approval or owner acceptance is recorded.

## Actual test
Command: `server/.venv/bin/python -m pytest server/tests/test_workspace_content.py::test_compound_missing_id_and_cross_workspace_references -v`.
Result: one test passed. The test creates a second workspace, attempts foreign parent/project references and foreign GET/PATCH/DELETE, and verifies that no issue is created in the original workspace.

## Uncovered scope and handoff
No browser keyboard test, narrow-screen relationship picker, back-navigation test or relation CRUD test was executed here. SMART-2 provides the proposed interaction contract. Delivery owner must identify or implement the scoped relation change, request code review, address findings and supply browser evidence before accepting this outcome.

## Captured source
SHA-256: 787c4fa1909fc9f77d703d0e95afb5816f84954a84492b12d6a9913fcb2249c7

```python
"""Authenticated local workspace content, without execution or integrations."""
from datetime import datetime, timezone
import json
import math
from uuid import uuid4
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select, update
from starlette.concurrency import run_in_threadpool

from workpal_backend.auth.dependencies import Principal, require_principal
from workpal_backend.auth.json_codec import user_response
from workpal_backend.auth.service import get_user
from workpal_backend.workspaces import service
from workpal_backend.workspaces.models import issue_status, members, workspaces
from . import repository as repo
from . import evidence

router = APIRouter()
COLLECTIONS = ('projects', 'issues', 'agents', 'skills', 'squads', 'autopilots', 'labels')
METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
UNAVAILABLE = 'This operation is unavailable in the local backend.'
ISSUE_DETAILS = {'evidence', 'comments', 'timeline', 'children', 'labels', 'task-runs', 'wakeups',
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
    workspace_id = request.headers.get('x-workspace-id')
    if not (slug and slug.strip()) and not workspace_id:
        raise HTTPException(400, 'X-Workspace-Slug is required')
    try:
        with request.app.state.database.transaction() as session:
            if slug and slug.strip():
                workspace = repo.resolve_workspace(session, principal, slug)
            else:
                service.require_workspace_access(session, principal, workspace_id)
                row = session.execute(select(workspaces).where(workspaces.c.id == workspace_id)).mappings().one_or_none()
                if row is None:
                    raise service.WorkspaceAccessError('workspace not found')
                workspace = dict(row)
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
    if kind == 'issues':
        if 'assignee_filters' in params:
            pairs = set()
            for token in params['assignee_filters'].split(','):
                actor_type, separator, identity = token.partition(':')
                if not separator or actor_type not in ('agent', 'squad', 'member') or not identity:
                    raise HTTPException(400, 'Invalid assignee filter')
                pairs.add((actor_type, identity))
            rows = [row for row in rows if (row.get('assignee_type'), row.get('assignee_id')) in pairs
                    or (params.get('include_no_assignee') == 'true' and not row.get('assignee_id'))]
        elif params.get('include_no_assignee') == 'true':
            rows = [row for row in rows if not row.get('assignee_id')]
        for field in ('assignee_id', 'assignee_type'):
            if field in params:
                rows = [row for row in rows if row.get(field) == params[field]]
        if params.get('sort') in ('created_at', 'updated_at'):
            rows.sort(key=lambda row: row.get(params['sort']) or '', reverse=params.get('direction') == 'desc')
    total = len(rows)
    rows = page(rows, params)
    return {kind: rows, 'total': total} if kind in ('projects', 'issues', 'labels', 'autopilots') else rows


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
    touched = set(body)
    for prefix in ('assignee', 'lead'):
        if touched & {prefix + '_id', prefix + '_type'}:
            touched.update({prefix + '_id', prefix + '_type'})
    validate_references(session, workspace, kind, {key: references.get(key) for key in
        ('project_id', 'parent_issue_id', 'runtime_id', 'assignee_id', 'assignee_type', 'lead_id', 'lead_type')
        if key in touched})
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
    saved = repo.put_record(session, workspace['id'], kind, row)
    if kind == 'issues':
        previous = old or {}
        before = (previous.get('assignee_type'), previous.get('assignee_id'))
        after = (row.get('assignee_type'), row.get('assignee_id'))
        if before != after:
            repo.put_record(session, workspace['id'], 'activities', {
                'id': str(uuid4()), 'workspace_id': workspace['id'], 'issue_id': record_id,
                'type': 'activity', 'action': 'assignee_changed', 'actor_type': 'member',
                'actor_id': principal.user_id, 'created_at': now,
                'details': {'from_type': before[0], 'from_id': before[1], 'to_type': after[0], 'to_id': after[1]},
            })
    return saved


def detail(session, workspace, principal, kind, record, operation, params=None):
    workspace_id, record_id = workspace['id'], record['id']
    if kind == 'issues':
        if operation == 'evidence':
            return evidence.inventory(session, workspace_id, record_id)
        if operation in ('comments', 'timeline'):
            comments = sorted((row for row in repo.list_records(session, workspace_id, 'comments')
                               if row.get('issue_id') == record_id), key=lambda row: row.get('created_at') or '')
            comments = [{**row, 'content': '**Evidence pending — this record has no verified delivery evidence.**\n\n' + str(row.get('content', ''))} if row.get('_fixture') else row for row in comments]
            comments = [{**row, 'content': '**Historical reference note — authored example, not a verified execution record.**\n\n' + str(row.get('content', ''))} if row.get('fixture_source') else row for row in comments]
            if operation == 'comments':
                return comments
            entries = [{**row, 'type': 'comment', 'comment_type': row.get('type'),
                        'actor_type': row.get('author_type'), 'actor_id': row.get('author_id')} for row in comments]
            entries.extend(row for row in repo.list_records(session, workspace_id, 'activities')
                           if row.get('issue_id') == record_id)
            return sorted(entries, key=lambda row: (row.get('created_at') or '', row['id']))
        if operation in ('task-runs', 'tasks', 'runs', 'attachments', 'activity'):
            collection = {'attachments': 'attachments', 'activity': 'activities'}.get(operation, 'task_runs')
            issue_ids = {record_id}
            if collection == 'task_runs' and (params or {}).get('scope') == 'subtree':
                issues = repo.list_records(session, workspace_id, 'issues')
                while True:
                    children = {row['id'] for row in issues if row.get('parent_issue_id') in issue_ids}
                    if children <= issue_ids:
                        break
                    issue_ids.update(children)
            rows = [row for row in repo.list_records(session, workspace_id, collection)
                    if row.get('issue_id') in issue_ids]
            return sorted(rows, key=lambda row: (row.get('created_at') or '', row['id']))
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
            if row is None and kind == 'issues' and request.method == 'GET':
                row = next((item for item in repo.list_records(session, workspace['id'], kind) if item.get('identifier') == record_path), None)
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
                    if kind == 'issues' and suffix == 'evidence' and request.method == 'POST':
                        return evidence.publish(session, workspace, principal, row, body)
                    if request.method == 'GET':
                        return detail(session, workspace, principal, kind, row, suffix, request.query_params)
                    if kind == 'issues' and suffix == 'comments' and request.method == 'POST':
                        if not isinstance(body.get('content'), str) or not body['content'].strip():
                            raise HTTPException(400, 'Comment content is required')
                        if set(body) - {'content', 'type', 'attachment_ids', 'suppress_agent_ids', 'steer_task_ids', 'parent_id'} or body.get('type', 'comment') != 'comment' or any(body.get(k) for k in ('attachment_ids', 'suppress_agent_ids', 'steer_task_ids', 'parent_id')):
                            raise HTTPException(501, UNAVAILABLE)
                        now = datetime.now(timezone.utc).isoformat()
                        comment = {'id': str(uuid4()), 'issue_id': record_id,
                                   'workspace_id': workspace['id'], 'content': body['content'],
                                   'type': 'comment', 'author_type': 'member', 'author_id': principal.user_id,
                                   'created_at': now, 'updated_at': now}
                        repo.put_record(session, workspace['id'], 'comments', comment)
                        return comment
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
    '/api/inbox/unread-summary': [], '/api/inbox/snoozed': [], '/api/properties': {'properties': []}, '/api/inbox': [], '/api/pins': [],
    '/api/issue-views': [], '/api/notifications': [], '/api/connected-apps': [],
}.items():
    router.add_api_route(_path, known_read_endpoint(_value), methods=METHODS)

def unavailable_projection(request: Request, principal: Principal = Depends(require_principal)):
    def operation(session, workspace):
        raise HTTPException(501, UNAVAILABLE)
    return execute(request, principal, operation)


for _path in ('/api/working-agents', '/api/agent-activity-30d', '/api/search-index/manifest'):
    router.add_api_route(_path, unavailable_projection, methods=METHODS)


router.add_api_route('/api/runtimes', known_read_endpoint(collection='runtimes'), methods=[method for method in METHODS if method != 'GET'])
router.add_api_route('/api/runtimes/{record_path:path}', record_endpoint('runtimes'), methods=METHODS)
router.add_api_route('/api/chat/sessions', known_read_endpoint(collection='sessions'), methods=METHODS)
router.add_api_route('/api/chat/sessions/{record_path:path}', record_endpoint('sessions'), methods=METHODS)

for _kind in COLLECTIONS:
    router.add_api_route(f'/api/{_kind}', collection_endpoint(_kind), methods=METHODS)
    router.add_api_route(f'/api/{_kind}/{{record_path:path}}', record_endpoint(_kind), methods=METHODS)


@router.api_route('/api/tasks/{task_id}/{operation}', methods=METHODS)
def task_detail(task_id: str, operation: str, request: Request, principal: Principal = Depends(require_principal)):
    def read(session, workspace):
        task = required_record(session, workspace['id'], 'task_runs', task_id)
        required_record(session, workspace['id'], 'issues', task['issue_id'])
        if request.method != 'GET':
            raise HTTPException(501, UNAVAILABLE)
        if operation == 'messages':
            return sorted((row for row in repo.list_records(session, workspace['id'], 'task_messages')
                           if row.get('task_id') == task_id), key=lambda row: row.get('seq', 0))
        if operation == 'context-receipt':
            return {'receipt': task.get('context_receipt')}
        raise HTTPException(501, UNAVAILABLE)
    return execute(request, principal, read)


@router.api_route('/api/attachments/{attachment_id}', methods=METHODS)
@router.api_route('/api/attachments/{attachment_id}/{operation}', methods=METHODS)
def attachment_detail(attachment_id: str, request: Request, operation: str = 'metadata',
                      principal: Principal = Depends(require_principal)):
    def read(session, workspace):
        attachment = required_record(session, workspace['id'], 'attachments', attachment_id)
        required_record(session, workspace['id'], 'issues', attachment['issue_id'])
        if request.method != 'GET':
            raise HTTPException(501, UNAVAILABLE)
        if operation in ('metadata', 'download-metadata'):
            return attachment
        if operation in ('content', 'download'):
            content = required_record(session, workspace['id'], 'attachment_contents', attachment_id)
            return Response(content['text'], media_type='text/plain', headers={
                'X-Original-Content-Type': attachment.get('content_type', 'text/plain'),
                'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, no-store',
            })
        raise HTTPException(501, UNAVAILABLE)
    return execute(request, principal, read)

```

## Original test output
```text
============================= test session starts ==============================
platform darwin -- Python 3.11.3, pytest-9.2.0, pluggy-1.7.0 -- /Users/patrick/Desktop/Workspace/ai-native/workpal/server/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/patrick/Desktop/Workspace/ai-native/workpal/server
configfile: pyproject.toml
plugins: anyio-4.16.0
collecting ... collected 1 item

server/tests/test_workspace_content.py::test_compound_missing_id_and_cross_workspace_references PASSED [100%]

=============================== warnings summary ===============================
server/.venv/lib/python3.11/site-packages/fastapi/testclient.py:1
  /Users/patrick/Desktop/Workspace/ai-native/workpal/server/.venv/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================= 1 passed, 1 warning in 1.04s =========================

```
