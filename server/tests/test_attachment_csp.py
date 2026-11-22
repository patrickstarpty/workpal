import pytest


@pytest.mark.parametrize(('raw', 'expected'), [
    (' https://EXAMPLE.com/path?q=x#f ', 'https://example.com'),
    ('HTTP://user:pass@LOCALHOST:5173/path', 'http://localhost:5173'),
    ('https://[::1]:443/', 'https://[::1]:443'),
    ('*', None), ('', None), ('//example.com', None),
    ('ftp://example.com', None), ('https:example.com', None),
    ('https://example.com/%zz', None), ('https://bad host', None),
    ('http://%ff.com', 'http://\ufffd.com'),
])
def test_frame_ancestor_origin(raw, expected):
    from workpal_backend.files.preview_security import normalize_frame_ancestor
    assert normalize_frame_ancestor(raw) == expected


def test_csp_keeps_self_and_deduplicates_normalized_origins():
    from workpal_backend.files.preview_security import preview_csp
    assert preview_csp(['https://EXAMPLE.com/path', '*', 'https://example.com', "'none'"]) == (
        "default-src 'none'; img-src 'self' data:; media-src 'self'; "
        "frame-ancestors 'self' https://example.com; object-src 'none'; "
        "base-uri 'none'; form-action 'none'")
