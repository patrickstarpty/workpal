"""Owner-authorized env reveal, fail-closed on audit persistence failure."""
import json
import secrets
import time
from uuid import UUID
from fastapi import APIRouter,Depends,Request,HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from workpal_backend.auth.dependencies import require_principal
from workpal_backend.infrastructure.database import DatabaseBusy
from workpal_backend.infrastructure.go_response import GoJSONResponse
from workpal_backend.infrastructure.go_uuid import parse_uuid
from workpal_backend.workspaces.admission import admit,read_member

router=APIRouter(default_response_class=GoJSONResponse)


def uuid7():
    # RFC 9562 timestamp layout; Go dbid.NewV7 uses the same wire version.
    value=(int(time.time()*1000)<<80)|(7<<76)|(secrets.randbits(12)<<64)|(2<<62)|secrets.randbits(62)
    return str(UUID(int=value))


def decode_env(raw):
    value=json.loads(raw) if raw else {}
    if not isinstance(value,dict) or any(v is not None and not isinstance(v,str) for v in value.values()):
        return {}
    return {k:value[k] or '' for k in sorted(value)}


def error(status,message):
    return GoJSONResponse({'error':message},status_code=status)


def authorize_env(id,request,principal):
    workspace,user,_=admit(request,principal)
    try:agent_id=parse_uuid(id)
    except ValueError:return error(400,'invalid agent id')
    database=request.app.state.database
    try:
        with database.transaction() as session:
            agent=session.execute(text('SELECT * FROM agent WHERE id=:id AND workspace_id=:workspace'),
                                  dict(id=agent_id,workspace=workspace)).mappings().one_or_none()
    except (SQLAlchemyError,DatabaseBusy):return error(404,'agent not found')
    if agent is None or agent['kind']!='user':return error(404,'agent not found')
    # Agent credentials are not yet issued by this backend; retain an explicit
    # guard at the boundary so adding that identity cannot expose this endpoint.
    if principal.identity_kind=='task_token':
        return error(403,'agents may not access env management endpoints')
    try:member=read_member(database,user,workspace)
    except HTTPException:return error(404,'agent not found')
    if member['role'] not in ('owner','admin','member'):
        return error(403,'insufficient permissions')
    if member['role'] not in ('owner','admin') and agent['owner_id']!=user:
        return error(403,"only the agent owner or a workspace owner/admin can manage this agent's env")
    return agent,user


@router.get('/api/agents/{id}/env')
def get_env(id:str,request:Request,principal=Depends(require_principal)):
    authorized=authorize_env(id,request,principal)
    if isinstance(authorized,GoJSONResponse):return authorized
    agent,user=authorized
    agent_id=agent['id']
    workspace=agent['workspace_id']
    database=request.app.state.database
    custom_env=decode_env(agent['custom_env'])
    details=dict(agent_id=agent_id,agent_name=agent['name'],revealed_keys=list(custom_env),key_count=len(custom_env))
    try:
        with database.transaction() as session:
            session.execute(text("INSERT INTO activity_log(id,workspace_id,actor_type,actor_id,action,details) VALUES (:id,:workspace,'member',:user,'agent_env_revealed',:details)"),
                            dict(id=uuid7(),workspace=workspace,user=user,details=json.dumps(details,ensure_ascii=False)))
    except (SQLAlchemyError,DatabaseBusy):
        return error(500,'audit log write failed; refusing to serve env without a recorded reveal')
    return GoJSONResponse(dict(agent_id=agent_id,custom_env=custom_env))


@router.put('/api/agents/{id}/env')
async def put_env(id:str,request:Request,principal=Depends(require_principal)):
    from starlette.concurrency import run_in_threadpool
    authorized=await run_in_threadpool(authorize_env,id,request,principal)
    if isinstance(authorized,GoJSONResponse):return authorized
    agent,user=authorized
    from .env_update import decode_update
    try:requested=decode_update(await request.body())
    except ValueError:return error(400,'invalid request body')
    return await run_in_threadpool(update_authorized,request,agent,user,requested)


def update_authorized(request,agent,user,requested):
    from .env_update import merge_env,persist_env,EnvWriteError
    from .projection import broadcast
    database=request.app.state.database
    merged,audit=merge_env(decode_env(agent['custom_env']),requested)
    if merged:
        try:
            with database.transaction() as session:
                provider=session.scalar(text('SELECT provider FROM agent_runtime WHERE id=:id AND workspace_id=:workspace'),
                    dict(id=agent['runtime_id'],workspace=agent['workspace_id']))
        except (SQLAlchemyError,DatabaseBusy):provider=None
        if provider=='qoder_cloud':
            return error(400,'Qoder agents take skills, tools, credentials and model from the Qoder Agent; remove them from this agent')
    try:updated=persist_env(database,agent,user,merged,audit)
    except EnvWriteError as exc:return error(500,str(exc))
    try:
        with database.transaction() as session:
            rows=session.execute(text('SELECT s.id,s.name,s.description,a.enabled FROM skill s JOIN agent_skill a ON a.skill_id=s.id WHERE a.agent_id=:id ORDER BY s.name ASC'),dict(id=agent['id'])).mappings().all()
            skills=[dict(id=r['id'],name=r['name'],description=r['description'],enabled=bool(r['enabled'])) for r in rows]
    except (SQLAlchemyError,DatabaseBusy):return error(500,'failed to load agent skills')
    request.app.state.events.publish(dict(type='agent:status',workspaceID=agent['workspace_id'],actorType='member',actorID=user,
        payload={'agent':broadcast(updated,skills)}))
    return GoJSONResponse(dict(agent_id=agent['id'],custom_env=merged))
