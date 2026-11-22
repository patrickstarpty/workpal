import pytest
from workpal_backend.realtime.protocol import parse_frame

@pytest.mark.parametrize('raw,reply',[
 ('{"TYPE":"ping"}',{'type':'pong'}),
 ('{"type":"ping","type":null}',{'type':'pong'}),
 ('{"type":7,"type":"ping"}',None),
 ('{"type":"ping","unknown":1e999}',{'type':'pong'}),
 ('{"type":"ping","unknown":NaN}',None),
 ('{"type":"ping"} {}',None),
 ('{"type":"subscribe","payload":{"SCOPE":"workspace","ID":"w"}}',{'type':'subscribe_ack','payload':{'scope':'workspace','id':'w'}}),
 ('{"type":"subscribe","payload":{"scope":"workspace","id":"w","id":null}}',{'type':'subscribe_ack','payload':{'scope':'workspace','id':'w'}}),
 ('{"type":"subscribe","payload":{"scope":"workspace","id":7,"id":"w"}}',{'type':'subscribe_error','payload':{'scope':'workspace','id':'w','error':'invalid payload'}}),
 ('{"type":"subscribe","payload":{"scope":"workspace","id":"w"},"payload":{"id":"w"}}',{'type':'subscribe_error','payload':{'scope':'','id':'w','error':'invalid payload'}}),
 ('{"type":"subscribe","payload":{"scope":"workspace","id":"w"},"payload":null}',{'type':'subscribe_error','payload':{'scope':'','id':'','error':'invalid payload'}}),
 ('{"type":"subscribe","payload":{"ſcope":"workspace","id":"w"}}',{'type':'subscribe_ack','payload':{'scope':'workspace','id':'w'}}),
 (b'{"type":"unsubscribe","payload":{"scope":"chat","id":"\xff"}}',{'type':'unsubscribe_ack','payload':{'scope':'chat','id':'\ufffd'}}),
])
def test_go_frame_decoding(raw,reply):
    assert parse_frame(raw,'w','u').reply==reply


def test_invalid_typed_field_never_calls_authorizer():
    def forbidden(*args):pytest.fail('invalid payload must not query authorization')
    result=parse_frame('{"type":"subscribe","payload":{"scope":7,"scope":"chat","id":"x"}}','w','u',authorizer=forbidden)
    assert result.reply['payload']['error']=='invalid payload'
