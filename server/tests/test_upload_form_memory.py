import asyncio
import pytest
from workpal_backend.files import upload_form
from test_upload_form import multipart


def test_file_memory_is_global_and_spilled_file_does_not_consume_remainder(monkeypatch):
    monkeypatch.setattr(upload_form,'MAX_FILE_SIZE',8)
    body=multipart([(f'Content-Disposition: form-data; name="other"; filename="{i}"'.encode(),value) for i,value in enumerate([b'a'*6,b'b'*6,b'c',b'd',b'e',b''])])
    async def run():
        form=await upload_form.parse_upload_form(body,'multipart/form-data; boundary=boundary')
        try:
            assert [f.file._rolled for f in form.files['other']]==[False,True,False,False,True,False]
            assert [await f.read() for f in form.files['other']]==[b'a'*6,b'b'*6,b'c',b'd',b'e',b'']
        finally:await form.close()
    asyncio.run(run())


def test_total_memory_charges_field_name_and_per_value_overhead(monkeypatch):
    monkeypatch.setattr(upload_form,'MAX_FORM_MEMORY',500)
    # Each value costs len(name)+200+len(value), even for duplicate map keys.
    body=multipart([(b'Content-Disposition: form-data; name="x"',b'a'*50)]*2)
    with pytest.raises(upload_form.UploadFormError):
        asyncio.run(upload_form.parse_upload_form(body,'multipart/form-data; boundary=boundary'))


def test_file_header_metadata_counts_against_global_memory(monkeypatch):
    monkeypatch.setattr(upload_form,'MAX_FORM_MEMORY',1000)
    body=multipart([(b'Content-Disposition: form-data; name="file"; filename="a"',b'')])
    # name+200 + (400+header-key+200+header-value) + 200+100 >1000.
    with pytest.raises(upload_form.UploadFormError):
        asyncio.run(upload_form.parse_upload_form(body,'multipart/form-data; boundary=boundary'))
