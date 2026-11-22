"""The frozen pgx UUID codec accepts 32 hex bytes or 36 bytes with four separators."""
import pytest
from workpal_backend.infrastructure.go_uuid import parse_uuid


@pytest.mark.parametrize('value', [
    '01234567-89ab-cdef-0123-456789abcdef',
    '0123456789abcdef0123456789abcdef',
    '01234567X89abYcdefZ0123W456789abcdef',
    '01234567-89AB-CDEF-0123-456789ABCDEF',
])
def test_pgtype_forms(value):
    assert parse_uuid(value) == '01234567-89ab-cdef-0123-456789abcdef'


@pytest.mark.parametrize('value', [
    '', None, 7, 'urn:uuid:01234567-89ab-cdef-0123-456789abcdef',
    '{01234567-89ab-cdef-0123-456789abcdef}',
    ' 0123456789abcdef0123456789abcdef ',
    'g123456789abcdef0123456789abcdef',
    '01234567é89ab-cdef-0123-456789abcdef',
])
def test_pgtype_rejections(value):
    with pytest.raises(ValueError):
        parse_uuid(value)
