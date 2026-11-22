import pytest
from workpal_backend.infrastructure.go_response import GoJSONResponse

@pytest.mark.parametrize('value,expected',[
    (1.0,b'1'),(-0.0,b'-0'),(1e-6,b'0.000001'),(1e-7,b'1e-7'),
    (1e20,b'100000000000000000000'),(1e21,b'1e+21'),
    (float(9007199254740993),b'9007199254740992'),
])
def test_go_float64_json_notation(value,expected):
    assert GoJSONResponse({'value':value}).body==b'{"value":'+expected+b'}\n'
