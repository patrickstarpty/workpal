import pytest


@pytest.mark.parametrize(('data','filename','mime'), [
    (b'', 'empty.bin', 'text/plain; charset=utf-8'),
    (b'\t <hTmL>', 'a.bin', 'text/html; charset=utf-8'),
    (b'<html\t>', 'a.bin', 'text/plain; charset=utf-8'),
    (b' \r<?xml x', 'a.bin', 'text/xml; charset=utf-8'),
    (b'%PDF-1.7', 'a.bin', 'application/pdf'),
    (b'\xff\xfe', 'a.bin', 'text/plain; charset=utf-8'),
    (b'\xff\xfe\x00\x00', 'a.bin', 'text/plain; charset=utf-16le'),
    (b'RIFFxxxxWEBPVP', 'a.bin', 'image/webp'),
    (b'RIFFxxxxWEBP', 'a.bin', 'text/plain; charset=utf-8'),
    (b'\x00\x00\x00\x18ftypisom0000mp42zzzz', 'a.bin', 'video/mp4'),
    (b'PK\x03\x04', 'a.bin', 'application/zip'),
    (b'a'*512+b'\x00', 'a.bin', 'text/plain; charset=utf-8'),
    (b'a'*511+b'\x00', 'a.bin', 'application/octet-stream'),
    (b'\x00', 'unsafe.SVG', 'image/svg+xml'),
    (b'<html>', 'file.JSON', 'application/json'),
    (b'\x00', 'a.json/', 'application/octet-stream'),
    (b'body{}', 'file.CSS', 'text/css'),
])
def test_upload_sniffs_bytes_then_applies_go_extension_overrides(data,filename,mime):
    from workpal_backend.files.mime_sniff import upload_content_type
    assert upload_content_type(data,filename)==mime
