"""Go attachment proxy's single-range policy for forward-only readers.

This does not implement the seekable ServeContent multipart response path.
"""
import re
from enum import IntEnum
from workpal_backend.auth.profile_decode import go_trim_space


class RangeOutcome(IntEnum):
    SATISFIABLE = 0
    UNSATISFIABLE = 1
    UNSUPPORTED = 2


def _int64(value):
    if not re.fullmatch(r'[+-]?[0-9]+', value):
        raise ValueError('invalid decimal integer')
    # Bound digit count before int(), including arbitrarily long zero prefixes.
    digits = value.lstrip('+-').lstrip('0') or '0'
    if len(digits) > 19:
        raise ValueError('integer overflow')
    number = int(('-' if value.startswith('-') else '') + digits)
    if not -(1 << 63) <= number < (1 << 63):
        raise ValueError('integer overflow')
    return number


def parse_single_byte_range(header, size):
    rejected = (0, 0, RangeOutcome.UNSATISFIABLE)
    unsupported = (0, 0, RangeOutcome.UNSUPPORTED)
    if not header.startswith('bytes='):
        return rejected
    spec = go_trim_space(header[6:])
    if not spec:
        return rejected
    if ',' in spec:
        return unsupported
    first, dash, last = spec.partition('-')
    if not dash:
        return rejected
    first, last = go_trim_space(first), go_trim_space(last)
    try:
        if not first:
            suffix = _int64(last)
            if suffix <= 0:
                return rejected
            if size == 0:
                return unsupported
            suffix = min(suffix, size)
            return size - suffix, suffix, RangeOutcome.SATISFIABLE
        start = _int64(first)
        if start < 0:
            return rejected
        if start >= size:
            return unsupported if size == 0 else rejected
        if not last:
            return start, size - start, RangeOutcome.SATISFIABLE
        end = _int64(last)
        if end < start:
            return rejected
        end = min(end, size - 1)
        return start, end - start + 1, RangeOutcome.SATISFIABLE
    except ValueError:
        return rejected
