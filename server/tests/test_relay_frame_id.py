import pytest
from workpal_backend.realtime.relay_frame import inject_event_id

@pytest.mark.parametrize('frame,event_id,expected',[
 (b'{ "z":9007199254740993, "a":1e999 }','id',b'{"a":1e999,"event_id":"id","z":9007199254740993}'),
 (b'{"nested": { "n":1.00, "s":"\\u0061 <>&" }}','id',b'{"event_id":"id","nested":{"n":1.00,"s":"\\u0061 \\u003c\\u003e\\u0026"}}'),
 (b'{"x":1,"x":2}','id',b'{"event_id":"id","x":2}'),
 (b' {"type":"x"}','id',b' {"type":"x"}'),
 (b'{ "event_id":null, "type":"x" }','id',b'{ "event_id":null, "type":"x" }'),
 (b'{"type":"x",}','id',b'{"type":"x",}'),
 (b'[]','id',b'[]'),(b'{ "x":1 }','',b'{ "x":1 }'),
])
def test_event_id_injection_preserves_raw_values(frame,event_id,expected):
    assert inject_event_id(frame,event_id)==expected


def test_deep_raw_payload_does_not_need_recursive_materialization():
    raw=b'{"payload":'+b'['*2000+b'1e999'+b']'*2000+b'}'
    assert inject_event_id(raw,'id')==b'{"event_id":"id","payload":'+b'['*2000+b'1e999'+b']'*2000+b'}'


def test_invalid_utf8_id_uses_go_replacement_escape_not_literal_rune():
    invalid=b'\xff'.decode('utf-8',errors='surrogateescape')
    assert inject_event_id(b'{}',invalid)==b'{"event_id":"\\ufffd"}'
    assert inject_event_id(b'{}','\ufffd')=='{"event_id":"\ufffd"}'.encode()
