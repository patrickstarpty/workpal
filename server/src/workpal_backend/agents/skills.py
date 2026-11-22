"""Canonical assignment summaries; skill source text is never executed."""
from fastapi import APIRouter,Depends,Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from workpal_backend.auth.dependencies import require_principal
from workpal_backend.infrastructure.database import DatabaseBusy
from workpal_backend.infrastructure.go_response import GoJSONResponse
from workpal_backend.infrastructure.go_json_value import decode_jsonb_value
from workpal_backend.infrastructure.go_uuid import parse_uuid
from workpal_backend.workspaces.admission import admit
from workpal_backend.runtimes.projection import timestamp
from .env import error

router=APIRouter(default_response_class=GoJSONResponse)


@router.get('/api/agents/{id}/skills')
def list_agent_skills(id:str,request:Request,principal=Depends(require_principal)):
    workspace,user,_=admit(request,principal)
    try:agent_id=parse_uuid(id)
    except ValueError:return error(400,'invalid agent id')
    database=request.app.state.database
    try:
        with database.transaction() as session:
            agent=session.execute(text('SELECT kind FROM agent WHERE id=:id AND workspace_id=:workspace'),
                                  dict(id=agent_id,workspace=workspace)).mappings().one_or_none()
    except (SQLAlchemyError,DatabaseBusy):return error(404,'agent not found')
    if agent is None or agent['kind']!='user':return error(404,'agent not found')
    try:
        with database.transaction() as session:
            rows=session.execute(text('''SELECT s.id,s.workspace_id,s.name,s.description,s.config,
                s.created_by,s.created_at,s.updated_at,a.enabled FROM skill s
                JOIN agent_skill a ON a.skill_id=s.id WHERE a.agent_id=:id ORDER BY s.name ASC'''),
                dict(id=agent_id)).mappings().all()
    except (SQLAlchemyError,DatabaseBusy):return error(500,'failed to list agent skills')
    return GoJSONResponse([dict(id=row['id'],workspace_id=row['workspace_id'],name=row['name'],
        description=row['description'],config=decode_jsonb_value(row['config']),created_by=row['created_by'],
        created_at=timestamp(row['created_at']),updated_at=timestamp(row['updated_at']),
        enabled=bool(row['enabled'])) for row in rows])
