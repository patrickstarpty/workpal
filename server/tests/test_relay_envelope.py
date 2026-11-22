from workpal_backend.realtime.relay_envelope import new_envelope,redis_values,envelope_from_values,peek_type_actor,stream_key,nodes_key,heartbeat_key


def test_envelope_fields_timestamp_and_original_bytes():
    frame=b'{ "type":"chat:message", "actor_id":"user", "payload":9007199254740993 }'
    env=new_envelope('node','workspace_member','w:u','exclude',frame,'event',clock_ns=lambda:1_234_000_000)
    assert env.event_type=='chat:message' and env.actor_id=='user'
    assert env.created_at=='1970-01-01T00:00:01.234Z' and env.workspace_id=='exclude'
    assert env.payload_json==frame
    values=redis_values(env)
    assert set(values)=={'event_id','event_type','scope','scope_id','workspace_id','actor_id','created_at','node_id','payload_json'}
    assert values['payload_json']==frame
    restored,valid=envelope_from_values(values)
    assert valid and restored==env


def test_partial_probe_keeps_valid_fields_but_new_envelope_requires_type():
    assert peek_type_actor(b'{"type":"x","actor_id":3,"actor_id":"u"}')==('x','u')
    assert peek_type_actor(b'{"type":7,"actor_id":"u"}')==('','u')
    env=new_envelope('n','s','i','',b'{"type":7,"actor_id":"u"}','e',clock_ns=lambda:0)
    assert env.event_type==env.actor_id==''
    assert peek_type_actor(b'{"TYPE":"x","ACTOR_ID":"u","type":null}')==('x','u')
    assert peek_type_actor(b'{"type":"x",}')==('','')
    assert peek_type_actor(b'{"type":"x","extra":'+b'['*2000+b'0'+b']'*2000+b'}')==('x','')


def test_redis_conversion_preserves_binary_and_rejects_other_value_types():
    env,valid=envelope_from_values({b'payload_json':b'\xffopaque',b'event_id':123,b'scope':b'chat'})
    assert valid and env.payload_json==b'\xffopaque' and env.event_id=='' and env.scope=='chat'
    assert redis_values(env)['payload_json']==b'\xffopaque'
    for value in [None,3,True,b'',{}]:assert not envelope_from_values({'payload_json':value})[1]
    assert new_envelope('n','s','i','',b'x','e',clock_ns=lambda:-1).created_at=='1969-12-31T23:59:59.999999999Z'
    assert stream_key('chat','a:b')=='ws:scope:chat:a:b:stream'
    assert nodes_key('','')=='ws:scope:::nodes'
    assert heartbeat_key('n')=='ws:node:n:heartbeat'
