"""Authenticated, workspace-scoped dashboard reads and contribution imports."""
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from workpal_backend.auth.dependencies import Principal, require_principal
from . import analytics
from .repository import get_record, list_records, put_record
from .routes import execute


router = APIRouter()


def aggregate(session, workspace, request):
    workspace_id = workspace['id']
    projects = list_records(session, workspace_id, 'projects')
    issues = list_records(session, workspace_id, 'issues')
    try:
        if request.url.path == '/api/dashboard/contribution':
            saved = get_record(session, workspace_id, 'contribution_data', 'workspace') or {}
            return analytics.contribution(projects, issues, saved.get('commits', []), request.query_params)
        runs = list_records(session, workspace_id, 'analytics_runs')
        return analytics.dashboard_rows(projects, issues, runs, request.url.path, request.query_params)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get('/api/dashboard/usage/daily')
@router.get('/api/dashboard/usage/by-agent')
@router.get('/api/dashboard/agent-runtime')
@router.get('/api/dashboard/runtime/daily')
@router.get('/api/dashboard/failures/daily')
@router.get('/api/dashboard/failures/by-agent')
@router.get('/api/dashboard/contribution')
def dashboard(request: Request, principal: Principal = Depends(require_principal)):
    return execute(request, principal, lambda session, workspace: aggregate(session, workspace, request))


@router.put('/api/dashboard/contribution')
async def replace_contribution(request: Request, principal: Principal = Depends(require_principal)):
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, 'invalid request') from None

    def replace(session, workspace):
        try:
            commits = analytics.validate_commits(body.get('commits') if isinstance(body, dict) else None)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        put_record(session, workspace['id'], 'contribution_data', {'id': 'workspace', 'commits': commits})
        return {'count': len(commits)}

    return await run_in_threadpool(execute, request, principal, replace)
