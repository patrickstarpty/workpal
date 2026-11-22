import pytest


@pytest.mark.parametrize(('mime', 'filename', 'allowed'), [
    (' TEXT/PLAIN ; charset=utf-8', 'file.bin', True),
    ('application/json; charset=utf8', 'file.bin', True),
    ('image/png', 'report.PY', True),
    ('image/png', 'C:\\folder\\Dockerfile', True),
    ('image/png', 'dir/.env/', True),
    ('image/png', 'dir/../Makefile', True),
    ('image/png', '.ENV', True),
    ('image/png', 'env', False),
    ('image/png', 'report.py ', False),
    ('application/pdf', 'file.pdf', False),
    ('application/octet-stream', 'test.İNİ', True),
    ('application/jsonx', 'file.bin', False),
])
def test_attachment_text_preview_whitelist(mime, filename, allowed):
    from workpal_backend.files.preview import is_text_previewable
    assert is_text_previewable(mime, filename) is allowed
