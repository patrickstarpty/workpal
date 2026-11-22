"""Canonical runtime listing; machine execution remains in separate protocols."""
from fastapi import APIRouter,Depends,Request,HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from workpal_backend.auth.dependencies import require_principal
from workpal_backend.infrastructure.database import DatabaseBusy
from workpal_backend.infrastructure.go_response import GoJSONResponse
from workpal_backend.workspaces.admission import admit,read_member,query_first
from .projection import public

router=APIRouter(default_response_class=GoJSONResponse)


@router.get('/api/runtimes')
def list_runtimes(request:Request,principal=Depends(require_principal)):
    workspace,user,_=admit(request,principal)
    # The actual Go handler checks membership again after middleware admission.
    member=read_member(request.app.state.database,user,workspace)
    clause=''
    if query_first(request,'owner')=='me':
        clause=' AND owner_id=:user'
    elif member['role'] not in ('owner','admin'):
        clause=""" AND (owner_id=:user OR visibility='public' OR
            (visibility='private' AND EXISTS
                (SELECT 1 FROM json_tree(agent_runtime.shared_with) WHERE type='text' AND workpal_uuid_text(value)=:user)))"""
    try:
        with request.app.state.database.transaction() as session:
            rows=session.execute(text('SELECT * FROM agent_runtime WHERE workspace_id=:workspace'+clause+
                ' ORDER BY workpal_timestamp_order(created_at) ASC'),dict(workspace=workspace,user=user)).mappings().all()
            # The local imported dataset predates canonical machine registration.
            # Expose its offline records only to local development administrators;
            # canonical runtimes and production visibility keep their own contract.
            if not rows and request.app.state.settings.dev_auth and member['role'] in ('owner','admin'):
                from workpal_backend.workspace_content.repository import list_records
                legacy = list_records(session, workspace, 'runtimes')
                if query_first(request,'owner') == 'me':
                    legacy = [row for row in legacy if row.get('owner_id') == user]
                return GoJSONResponse([{**row, 'status': 'offline', 'custom_name': row.get('custom_name') or row.get('name')} for row in legacy])
            return GoJSONResponse([public(row) for row in rows])
    except (SQLAlchemyError,DatabaseBusy):
        return GoJSONResponse({'error':'failed to list runtimes'},status_code=500)
