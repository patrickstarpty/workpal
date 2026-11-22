import pytest
from workpal_backend.realtime.protocol import parse_frame

@pytest.mark.parametrize('depth',[900,1100,2000,9999])
def test_unknown_nested_arrays_do_not_drop_valid_ping(depth):
    raw='{"type":"ping","unknown":'+'['*depth+'0'+']'*depth+'}'
    assert parse_frame(raw,'w','u').reply=={'type':'pong'}


def test_depth_limit_counts_outer_object_and_rejects_invalid_deep_syntax():
    raw='{"type":"ping","unknown":'+'['*10000+'0'+']'*10000+'}'
    assert parse_frame(raw,'w','u').reply is None
    for leaf in ['[1,]','{"x":}','{"x":1,}','01','1.','1e+','NaN','"bad\\x"','[true false]']:
        raw='{"type":"ping","unknown":'+'['*1100+leaf+']'*1100+'}'
        assert parse_frame(raw,'w','u').reply is None


def test_nested_objects_and_subscription_fields_survive_unknown_payload_tree():
    raw='{"type":"subscribe","payload":{"scope":"workspace","id":"w","unknown":'+'{"x":'*1100+'null'+'}'*1100+'}}'
    assert parse_frame(raw,'w','u').reply=={'type':'subscribe_ack','payload':{'scope':'workspace','id':'w'}}
    raw='{"type":"subscribe","payload":{"scope":'+'['*1100+'0'+']'*1100+',"scope":"workspace","id":"w"}}'
    assert parse_frame(raw,'w','u').reply['payload']['error']=='invalid payload'
