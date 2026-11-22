import pytest
from workpal_backend.files.upload_form import UploadForm


@pytest.mark.parametrize(('query','expected'), [
    (b'', 'multipart-first'),
    (b'issue_id=query&issue_id=second', 'query'),
    (b'issue_id=&issue_id=second', ''),
    (b'issue_id', ''),
    (b'issue_id=bad%zz&issue_id=valid', 'valid'),
    (b'issue_id=bad;ignored&other=x', 'multipart-first'),
    (b'issue%5fid=hello+world', 'hello world'),
    (b'issue_id=%ff', '\udcff'),
])
def test_query_precedes_multipart_even_when_empty(query,expected):
    from workpal_backend.files.form_values import form_value
    form=UploadForm({'issue_id':['multipart-first','multipart-second']},{})
    assert form_value(form, 'issue_id', query)==expected


def test_file_parts_do_not_supply_form_values():
    from workpal_backend.files.form_values import form_value
    assert form_value(UploadForm({}, {'issue_id':[object()]}),'issue_id',b'')==''


@pytest.mark.parametrize('query',[b'issue_id=bad%zz&issue_id=valid',b'issue_id=bad;ignored',b'other=%',b'%zz=x'])
def test_upload_rejects_query_parse_errors_even_with_valid_form(query):
    import asyncio
    from workpal_backend.files.upload_form import parse_upload_form,UploadFormError
    body=b'--boundary--\r\n'
    with pytest.raises(UploadFormError) as error:
        asyncio.run(parse_upload_form(body,'multipart/form-data; boundary=boundary',raw_query=query))
    assert error.value.status==400
