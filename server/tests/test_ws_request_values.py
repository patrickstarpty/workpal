

def test_query_first_value_and_invalid_component_rules():
    from workpal_backend.realtime.request_values import query_value
    assert query_value(b'workspace_id=&workspace_id=later','workspace_id')==''
    assert query_value(b'workspace_id=bad%zz&workspace_id=good','workspace_id')=='good'
    assert query_value(b'workspace_id=bad;ignored&workspace_id=good','workspace_id')=='good'
    assert query_value(b'workspace%5fid=a+b','workspace_id')=='a b'
    assert query_value(b'workspace_id=%ff','workspace_id').encode('utf8','surrogateescape')==b'\xff'


def test_cookie_first_valid_occurrence_including_empty_and_limit():
    from workpal_backend.realtime.request_values import first_cookie
    assert first_cookie(['workpal_auth=; workpal_auth=second'],'workpal_auth')==''
    assert first_cookie(['workpal_auth="first"','workpal_auth=second'],'workpal_auth')=='first'
    assert first_cookie(['workpal_auth=bad\\value; workpal_auth=good'],'workpal_auth')=='good'
    assert first_cookie(['workpal_auth= value '],'workpal_auth')==' value'
    assert first_cookie(['workpal_auth=first;'+'x=1;'*2999],'workpal_auth') is None
