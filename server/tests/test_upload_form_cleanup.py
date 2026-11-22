import asyncio
import tempfile
import pytest
from workpal_backend.files import upload_form


@pytest.mark.parametrize('failure', ['read', 'cancel', 'malformed', 'write'])
def test_owned_upload_files_close_on_failure(monkeypatch, failure):
    opened=[]
    class FailingFile:
        def __init__(self):self.file=tempfile.SpooledTemporaryFile()
        def tell(self):return self.file.tell()
        def write(self,data):raise OSError('disk write failed')
        def close(self):self.file.close()
        @property
        def closed(self):return self.file.closed
        @property
        def _rolled(self):return False
    def spool(**kwargs):
        result=FailingFile() if failure=='write' else tempfile.SpooledTemporaryFile(**kwargs)
        opened.append(result)
        return result
    monkeypatch.setattr(upload_form,'SpooledTemporaryFile',spool)
    async def source():
        yield b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="a"\r\n\r\n'
        yield b'content'
        if failure=='read':raise OSError('client read failed')
        if failure=='cancel':raise asyncio.CancelledError()
        if failure=='malformed':yield b'\r\n--boundary--\r'
        else:yield b'\r\n--boundary--\r\n'
    exception=asyncio.CancelledError if failure=='cancel' else upload_form.UploadFormError
    with pytest.raises(exception) as error:
        asyncio.run(upload_form.parse_upload_form(source(),'multipart/form-data; boundary=boundary'))
    if failure!='cancel':assert error.value.status==400
    assert len(opened)==1
    assert opened[0].closed
