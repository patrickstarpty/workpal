"""Go Redis relay envelope; payload bytes stay opaque until frame injection."""
from dataclasses import dataclass,fields
from datetime import datetime,timezone
import time
from .frame_decode import _typed_layers,_fold
from ..auth.profile_decode import _Object,_replace_surrogates


def stream_key(scope,identity):return f'ws:scope:{scope}:{identity}:stream'
def nodes_key(scope,identity):return f'ws:scope:{scope}:{identity}:nodes'
def heartbeat_key(node):return f'ws:node:{node}:heartbeat'

@dataclass(frozen=True)
class Envelope:
    event_id: str=''
    event_type: str=''
    scope: str=''
    scope_id: str=''
    workspace_id: str=''
    actor_id: str=''
    created_at: str=''
    node_id: str=''
    payload_json: bytes=b''


def peek_type_actor(frame):
    try:value=_typed_layers(_replace_surrogates(frame.decode('utf-8',errors='surrogateescape')))
    except (ValueError,UnicodeError):return '',''
    if not isinstance(value,_Object):return '',''
    result={'TYPE':'','ACTOR_ID':''}
    for key,item in value:
        field=_fold(key)
        if field in result and isinstance(item,str):result[field]=_replace_surrogates(item)
    # Go ignores Unmarshal's type error and returns its partially filled struct.
    return result['TYPE'],result['ACTOR_ID']


def _timestamp(nanoseconds):
    seconds,nanos=divmod(nanoseconds,1_000_000_000)
    date=datetime.fromtimestamp(seconds,timezone.utc)
    prefix=f'{date.year:04}-{date.month:02}-{date.day:02}T{date.hour:02}:{date.minute:02}:{date.second:02}'
    return prefix+('.'+f'{nanos:09}'.rstrip('0') if nanos else '')+'Z'


def new_envelope(node,scope,identity,exclude,frame,event_id,*,clock_ns=time.time_ns):
    kind,actor=peek_type_actor(frame)
    return Envelope(event_id=event_id,event_type=kind,scope=scope,scope_id=identity,
                    workspace_id=exclude,actor_id=actor if kind else '',created_at=_timestamp(clock_ns()),
                    node_id=node,payload_json=frame)


def _redis_bytes(value):
    if isinstance(value,bytes):return value
    if isinstance(value,str):return value.encode('utf-8',errors='surrogateescape')
    return b''


def redis_values(envelope):
    return {field.name:_redis_bytes(getattr(envelope,field.name)) for field in fields(Envelope)}


def envelope_from_values(values):
    data={}
    for field in fields(Envelope):
        raw=_redis_bytes(values.get(field.name,values.get(field.name.encode())))
        data[field.name]=raw if field.name=='payload_json' else raw.decode('utf-8',errors='surrogateescape')
    envelope=Envelope(**data)
    return envelope,bool(envelope.payload_json)
