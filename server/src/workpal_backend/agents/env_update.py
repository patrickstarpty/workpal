"""Env replacement primitives shared by the canonical update handler.

The caller authorizes and validates first; post-commit skill loading and
redacted publication belong to the HTTP handler, as in Go UpdateAgentEnv.
"""
import json
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from workpal_backend.infrastructure.database import DatabaseBusy
from .env import uuid7


class EnvWriteError(Exception):
    """A Go-compatible update/audit failure after transaction rollback."""


def merge_env(existing,requested):
    merged={}
    audit={key:[] for key in ('added_keys','removed_keys','changed_keys','preserved_keys')}
    for key,value in requested.items():
        if value=='****':
            if key in existing:
                merged[key]=existing[key]
                audit['preserved_keys'].append(key)
            continue
        merged[key]=value
        if key not in existing:audit['added_keys'].append(key)
        elif existing[key]!=value:audit['changed_keys'].append(key)
    audit['removed_keys']=[key for key in existing if key not in requested]
    # Go's untouched nil slices marshal as null, not [].
    return dict(sorted(merged.items())),{key:sorted(values) or None for key,values in audit.items()}


def persist_env(database,agent,user_id,merged,audit):
    message='failed to update env'
    try:
        with database.transaction() as session:
            updated=dict(session.execute(text('UPDATE agent SET custom_env=:env,updated_at=workpal_now() WHERE id=:id RETURNING *'),
                dict(env=json.dumps(merged,ensure_ascii=False),id=agent['id'])).mappings().one())
            message='audit log write failed; env update rolled back'
            details=dict(agent_id=agent['id'],agent_name=agent['name'],**audit)
            session.execute(text("INSERT INTO activity_log(id,workspace_id,actor_type,actor_id,action,details) VALUES (:id,:workspace,'member',:user,'agent_env_updated',:details)"),
                dict(id=uuid7(),workspace=agent['workspace_id'],user=user_id,details=json.dumps(details,ensure_ascii=False)))
            message='failed to update env'
        return updated
    except (SQLAlchemyError,DatabaseBusy) as exc:
        raise EnvWriteError(message) from exc


def decode_update(raw):
    """Decode one Go request struct, retaining duplicate-map merge semantics."""
    import re
    from workpal_backend.auth.profile_decode import _Object,_replace_surrogates,_invalid_constant
    source=_replace_surrogates(raw.decode('utf-8',errors='surrogateescape'))
    try:
        value,_=json.JSONDecoder(object_pairs_hook=_Object,parse_constant=_invalid_constant,
            parse_int=lambda value:0,parse_float=lambda value:0).raw_decode(
            source,re.match(r'[ \t\r\n]*',source).end())
        if value is None:return {}
        if not isinstance(value,_Object):raise ValueError()
        result={}
        for key,item in value:
            folded=''.join(c.upper() if 'a'<=c<='z' else 'S' if c=='ſ' else 'K' if c=='K' else c for c in key)
            if folded!='CUSTOM_ENV':continue
            if item is None:
                result={}
                continue
            if not isinstance(item,_Object):raise ValueError()
            for name,entry in item:
                if entry is not None and not isinstance(entry,str):raise ValueError()
                result[_replace_surrogates(name)]=_replace_surrogates(entry) if entry is not None else ''
        return result
    except (ValueError,RecursionError,OverflowError) as exc:
        raise ValueError('invalid request body') from exc
