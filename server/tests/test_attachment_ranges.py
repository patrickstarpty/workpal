import pytest


@pytest.mark.parametrize(('header', 'size', 'expected'), [
    ('bytes=2-4', 10, (2, 3, 0)),
    ('bytes=2-', 10, (2, 8, 0)),
    ('bytes=-3', 10, (7, 3, 0)),
    ('bytes=-30', 10, (0, 10, 0)),
    ('bytes=2-40', 10, (2, 8, 0)),
    ('bytes=10-', 10, (0, 0, 1)),
    ('bytes=4-2', 10, (0, 0, 1)),
    ('bytes=0-invalid', 0, (0, 0, 2)),
    ('bytes=-0', 0, (0, 0, 1)),
    ('bytes=garbage,garbage', 10, (0, 0, 2)),
    ('bytes=+2-+4', 10, (2, 3, 0)),
    ('bytes=２-４', 10, (0, 0, 1)),
    ('bytes=9223372036854775808-', 10, (0, 0, 1)),
    ('bytes=\u00852\u00a0-\u20034', 10, (2, 3, 0)),
    ('Bytes=0-1', 10, (0, 0, 1)),
])
def test_forward_only_attachment_range(header, size, expected):
    from workpal_backend.files.ranges import parse_single_byte_range
    assert parse_single_byte_range(header, size) == expected
