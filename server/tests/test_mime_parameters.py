import pytest


@pytest.mark.parametrize(('raw','expected'), [
    (' FORM-DATA ; name="file"; filename="C:\\dir\\file.txt"',('form-data',{'name':'file','filename':'C:\\dir\\file.txt'},None)),
    ('text/plain; X=a; x=a',('text/plain',{'x':'a'},None)),
    ('text/plain; x=a; x=b',('',None,'mime: duplicate parameter name')),
    ('text/plain;',('text/plain',{},None)),
    ('text/plain;;',('text/plain',None,'mime: invalid media parameter')),
    ('text/plain; x=""',('text/plain',{'x':''},None)),
    ('text/plain; x=',('text/plain',None,'mime: invalid media parameter')),
    ('text',('text',{},None)),
    ('text /plain',('',None,'mime: expected slash after first token')),
    ('text/',('',None,'mime: expected token after slash')),
    ('',('',None,'mime: no media type')),
    ('form-data; filename=plain; filename*=utf-8\'\'%E4%B8%AD.txt',('form-data',{'filename':'中.txt'},None)),
    ('form-data; filename=plain; filename*=other\'\'ignored',('form-data',{'filename':'plain'},None)),
    ('form-data; filename*0*=utf-8\'\'a%20; filename*1=b; filename*2*=%ff',('form-data',{'filename':'a b\udcff'},None)),
    ('form-data; filename*0*=utf-8\'\'%E4; filename*1*=%B8%AD',('form-data',{'filename':'中'},None)),
])
def test_go_media_parameters(raw,expected):
    from workpal_backend.files.mime_parameters import parse_media_type
    assert parse_media_type(raw)==expected
