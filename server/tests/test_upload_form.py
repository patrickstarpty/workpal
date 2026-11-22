import asyncio
import pytest


def multipart(parts, boundary=b'boundary'):
    return b''.join(b'--'+boundary+b'\r\n'+headers+b'\r\n\r\n'+body+b'\r\n' for headers,body in parts)+b'--'+boundary+b'--\r\n'


def test_form_keeps_first_file_empty_filenames_as_values_and_skips_unnamed():
    from workpal_backend.files.upload_form import parse_upload_form
    async def run():
        body=multipart([
            (b'Content-Disposition: form-data; name="file"; filename="first.txt"',b'first'),
            (b'Content-Disposition: form-data; name="file"; filename="second.txt"',b'second'),
            (b'Content-Disposition: form-data; name="file"; filename=""',b'field'),
            (b'Content-Disposition: form-data; filename="ignored.txt"',b'ignored'),
            (b'Content-Disposition: attachment; name="ignored"',b'ignored'),
            (b'Content-Disposition: form-data; name="issue_id"',b'first-id'),
            (b'Content-Disposition: form-data; name="issue_id"',b'second-id'),
        ])
        form=await parse_upload_form(body,'multipart/form-data; boundary=boundary')
        try:
            assert form.first_file().filename=='first.txt'
            assert await form.first_file().read()==b'first'
            assert len(form.files['file'])==2
            assert form.values=={'file':['field'],'issue_id':['first-id','second-id']}
            assert form.value('issue_id')=='first-id'
        finally:await form.close()
        assert all(f.file.closed for files in form.files.values() for f in files)
    asyncio.run(run())


def test_form_uses_go_filename_and_first_content_disposition():
    from workpal_backend.files.upload_form import parse_upload_form
    async def run():
        body=multipart([(b'Content-Disposition: form-data; name="file"; filename="C:\\dir\\a.txt"\r\nContent-Disposition: form-data; name="other"; filename="b.txt"',b'body')])
        form=await parse_upload_form(body,'multipart/form-data; boundary=boundary')
        try:assert form.first_file().filename=='C:\\dir\\a.txt'
        finally:await form.close()
    asyncio.run(run())


@pytest.mark.parametrize('body',[b'',b'broken',b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="x"\r\n\r\nunfinished'])
def test_form_rejects_truncation(body):
    from workpal_backend.files.upload_form import parse_upload_form, UploadFormError
    with pytest.raises(UploadFormError) as exc:asyncio.run(parse_upload_form(body,'multipart/form-data; boundary=boundary'))
    assert exc.value.status==400


def test_metadata_is_not_limited_to_starlette_one_megabyte():
    from workpal_backend.files.upload_form import parse_upload_form
    async def run():
        value=b'm'*(1024*1024+1)
        form=await parse_upload_form(multipart([(b'Content-Disposition: form-data; name="description"',value)]),'multipart/form-data; boundary=boundary')
        try:assert len(form.value('description'))==len(value)
        finally:await form.close()
    asyncio.run(run())


@pytest.mark.parametrize(('encoded','decoded','valid'), [
    (b'a=3Db=0A',b'a=b\n',True),
    (b'a  \r\nb\t',b'a\r\nb',True),
    (b'a=\r\nb',b'ab',True),
    (b'end=',b'end',True),
    (b'=',b'',False),
    (b'a\x00b',b'',False),
    (b'raw\xff',b'raw\xff',True),
    (b'a'*4097,b'',False),
])
def test_quoted_printable_follows_go_reader(encoded,decoded,valid):
    from workpal_backend.files.upload_form import parse_upload_form, UploadFormError
    async def run():
        body=multipart([(b'Content-Disposition: form-data; name="file"; filename="a"\r\nContent-Transfer-Encoding: quoted-printable',encoded)])
        if not valid:
            with pytest.raises(UploadFormError):await parse_upload_form(body,'multipart/form-data; boundary=boundary')
            return
        form=await parse_upload_form(body,'multipart/form-data; boundary=boundary')
        try:assert await form.first_file().read()==decoded
        finally:await form.close()
    asyncio.run(run())


@pytest.mark.parametrize('variant',['preamble','folded','lf','truncated_cr'])
def test_go_multipart_boundary_and_header_rules(variant):
    from workpal_backend.files.upload_form import parse_upload_form, UploadFormError
    async def run():
        header=b'Content-Disposition: form-data; name="file"; filename="a"'
        if variant=='folded':header=b'Content-Disposition: form-data;\r\n name="file"; filename="a"'
        body=multipart([(header,b'a\nraw\r\nbytes')])
        if variant=='preamble':body=b'ignored preamble\n'+body
        if variant=='lf':body=body.replace(b'\r\n',b'\n')
        if variant=='truncated_cr':
            with pytest.raises(UploadFormError):await parse_upload_form(body[:-1],'multipart/form-data; boundary=boundary')
            return
        form=await parse_upload_form(body,'multipart/form-data; boundary=boundary')
        try:assert await form.first_file().read()==(b'a\nraw\nbytes' if variant=='lf' else b'a\nraw\r\nbytes')
        finally:await form.close()
    asyncio.run(run())


def test_invalid_quoted_printable_stops_before_consuming_rest_of_request():
    from workpal_backend.files.upload_form import parse_upload_form, UploadFormError
    async def body():
        yield b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="a"\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n'
        yield b'a'*4096
        raise AssertionError('Parser consumed bytes after the Go decoder would fail')
    with pytest.raises(UploadFormError):
        asyncio.run(parse_upload_form(body(),'multipart/form-data; boundary=boundary'))


@pytest.mark.parametrize('variant', ['exact_eof_buffer', 'space_header'])
def test_original_go_accepts_exact_qp_eof_and_spaced_header(variant):
    from workpal_backend.files.upload_form import parse_upload_form
    async def run():
        header=b'Content-Disposition: form-data; name="file"; filename="a"'
        payload=b'body'
        if variant=='exact_eof_buffer':
            header+=b'\r\nContent-Transfer-Encoding: quoted-printable'
            payload=b'a'*4096
        else:header+=b'\r\nX-Test : value'
        form=await parse_upload_form(multipart([(header,payload)]),'multipart/form-data; boundary=boundary')
        try:assert await form.first_file().read()==payload
        finally:await form.close()
    asyncio.run(run())
