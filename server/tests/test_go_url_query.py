import pytest


@pytest.mark.parametrize(('raw','expected'),[
    ('https://cdn.test/a?z=2&a=1&a=3','https://cdn.test/a?a=1&a=3&download=a+b&z=2'),
    ('https://cdn.test/a?bad=%zz&x=1;ignored','https://cdn.test/a?download=a+b'),
    ('HTTPS://cdn.test/a%2fb#part','https://cdn.test/a%2fb?download=a+b#part'),
    ('https:/a','https:/a?download=a+b'),
    ('https://cdn.test/中文','https://cdn.test/%E4%B8%AD%E6%96%87?download=a+b'),
    ('https://user:p:a@cdn.test/a','https://user:p%3Aa@cdn.test/a?download=a+b'),
    ('https://cdn.test/a?download=old&download=other','https://cdn.test/a?download=a+b'),
    ('https://cdn.test/a%zz','https://cdn.test/a%zz'),
    ('http:opaque%zz','http:opaque%zz?download=a+b'),
    ('//cdn.test/a','//cdn.test/a?download=a+b'),
    ('relative path#f f','relative%20path?download=a+b#f%20f'),
])
def test_go_parse_set_query_and_string(raw,expected):
    from workpal_backend.infrastructure.go_url_query import set_query_value
    assert set_query_value(raw,'download','a b')==expected
