import pytest
from workpal_backend.auth import profile_decode as subject


@pytest.mark.parametrize('raw,want', [
    (b'null', {}), (b' {} {}', {}), (b'{}garbage', {}),
    (b'{"NAME":"Ada","name":null}', {'name': None}),
    (b'{"name":null,"Name":"Ada"}', {'name': 'Ada'}),
    (b'{"unknown":{"name":7},"LANGUAGE":"en"}', {'language': 'en'}),
    (b'{"name":"\\ud800x\\udc00"}', {'name': '\ufffdx\ufffd'}),
    (b'{"name":"\\ud83d\\ude00"}', {'name': '😀'}),
    (b'{"name":"\xff\xed\xa0\x80"}', {'name': '\ufffd' * 4}),
    ('{"profile_description":"你好","avatar_url":"","timezone":null}'.encode(),
     {'profile_description': '你好', 'avatar_url': '', 'timezone': None}),
    (b'\r\n\t null trailing', {}),
])
def test_decode(raw, want):
    assert subject.decode_profile_patch(raw) == want


@pytest.mark.parametrize('raw', [b'', b' ', b'[]', b'"{}"', b'1', b'true',
    b'{"name":7,"name":"Ada"}', b'{"name":[],"name":null}',
    b'{"name":{}}', b'{"name":false}', b'{"unknown":NaN}',
    b'{"unknown":Infinity}', b'{"unknown":-Infinity}', b'{"name":"x",}',
    b'{"unknown":[}', b'{"name":"\x01"}', b'\xef\xbb\xbf{}'])
def test_reject(raw):
    with pytest.raises(subject.ProfileDecodeError):
        subject.decode_profile_patch(raw)


def test_trim():
    assert subject.go_trim_space('\t\n\v\f\r \x85\xa0\u1680\u2000\u200a\u2028\u2029\u202f\u205f\u3000你好 \t') == '你好'
    assert subject.go_trim_space(' \x1c\x1d\x1e\x1f ') == '\x1c\x1d\x1e\x1f'


def test_field_names_use_go_simple_fold_not_unicode_upper_expansion():
    assert subject.decode_profile_patch('{"tımezone":"bad","profıle_description":"bad"}'.encode()) == {}
    assert subject.decode_profile_patch('{"profile_deſcription":"ok","TIMEZONE":"UTC"}'.encode()) == {
        'profile_description': 'ok', 'timezone': 'UTC'}
