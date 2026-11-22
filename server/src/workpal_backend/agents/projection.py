"""Go agent broadcast projection; secret-bearing configuration is redacted."""
import json
from pathlib import Path
from workpal_backend.infrastructure.go_json_value import decode_jsonb_value
from workpal_backend.runtimes.projection import timestamp
from workpal_backend.auth.profile_decode import go_trim_space


def struct_array(raw,required,optional=(),null_empty=True):
    value=json.loads(raw) if raw else None
    if value is None:return [] if null_empty else None
    if not isinstance(value,list):return []
    result=[]
    for item in value:
        out=dict.fromkeys(required,'')
        if item is not None:
            if not isinstance(item,dict):return []
            for key,val in sorted(item.items(),key=lambda pair:(len(pair[0].encode()),pair[0].encode())):
                folded=''.join(c.upper() if 'a'<=c<='z' else 'S' if c=='ſ' else 'K' if c=='K' else c for c in key)
                name=next((k for k in (*required,*optional) if k.upper()==folded),None)
                if name is None or val is None:continue
                if not isinstance(val,str):return []
                if val or name in required:out[name]=val
                else:out.pop(name,None)
        result.append(out)
    return result


def broadcast(agent,skills):
    rc=decode_jsonb_value(agent['runtime_config'])
    if isinstance(rc,dict) and isinstance(rc.get('gateway'),dict):
        token=rc['gateway'].get('token')
        if isinstance(token,str) and token:rc['gateway']['token']='***'
    args=json.loads(agent['custom_args'])
    args=[value if isinstance(value,str) else '' for value in args] if isinstance(args,list) else []
    env=json.loads(agent['custom_env'])
    count=len(env) if isinstance(env,dict) else 0
    result=dict(id=agent['id'],workspace_id=agent['workspace_id'],runtime_id=agent['runtime_id'] or '',
        runtime_bound=agent['runtime_id'] is not None,name=agent['name'],description=agent['description'],
        instructions=agent['instructions'],conversation_starters=struct_array(agent['conversation_starters'],('label','prompt'),null_empty=False))
    if agent['system_key']:
        result['system_key']=agent['system_key']
        if agent['system_key']=='mika':
            name=go_trim_space(agent['name']) or 'Mika'
            result['system_instructions']=Path(__file__).with_name('mika_instructions.txt').read_text().rstrip('\n').replace('{{AGENT_NAME}}',name)
    result.update(avatar_url=agent['avatar_url'],runtime_mode=agent['runtime_mode'],runtime_config=rc,
        custom_args=args,mcp_config=None,has_custom_env=count>0,custom_env_key_count=count,
        mcp_config_redacted=agent['mcp_config'] is not None,visibility=agent['visibility'],
        permission_mode=agent['permission_mode'],invocation_targets=[],status=agent['status'],
        max_concurrent_tasks=agent['max_concurrent_tasks'],model=agent['model'] or '',
        thinking_level=agent['thinking_level'] or '',service_tier=agent['service_tier'] or '')
    if agent['composio_toolkit_allowlist'] is not None:
        result['composio_toolkit_allowlist_redacted']=True
    result.update(owner_id=agent['owner_id'],skills=skills,
        disabled_runtime_skills=struct_array(agent['disabled_runtime_skills'],('runtime_id','provider','root','key'),('name','plugin')),
        created_at=timestamp(agent['created_at']),updated_at=timestamp(agent['updated_at']),
        archived_at=timestamp(agent['archived_at']),archived_by=agent['archived_by'])
    return result
