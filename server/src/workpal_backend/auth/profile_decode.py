"""Decode the bounded profile request without collapsing duplicate members."""
import json
import re


class ProfileDecodeError(ValueError):
    """The first JSON value is not a valid profile patch."""


class _Object(list):
    pass


_FIELDS = ('name', 'avatar_url', 'language', 'profile_description', 'timezone')
_SPACE = '\t\n\v\f\r \x85\xa0\u1680' + ''.join(map(chr, range(0x2000, 0x200B))) + '\u2028\u2029\u202f\u205f\u3000'


def go_trim_space(value: str) -> str:
    return value.strip(_SPACE)


def _invalid_constant(value: str):
    raise ProfileDecodeError('invalid request body')


def _replace_surrogates(value: str) -> str:
    return ''.join('\ufffd' if 0xD800 <= ord(char) <= 0xDFFF else char for char in value)


def decode_profile_patch(raw: bytes) -> dict[str, str | None]:
    # surrogateescape preserves each invalid byte so each becomes one replacement.
    source = _replace_surrogates(raw.decode('utf-8', errors='surrogateescape'))
    try:
        value, _ = json.JSONDecoder(object_pairs_hook=_Object,
                                    parse_constant=_invalid_constant).raw_decode(
                                        source, re.match(r'[ \t\r\n]*', source).end())
    except (ValueError, RecursionError) as exc:
        raise ProfileDecodeError('invalid request body') from exc
    if value is None:
        return {}
    if not isinstance(value, _Object):
        raise ProfileDecodeError('invalid request body')
    patch = {}
    for key, item in value:
        # Go SimpleFold only brings long-s and Kelvin sign into ASCII cycles.
        # Python upper() additionally maps dotless-i and expands some characters.
        folded = ''.join(char.upper() if 'a' <= char <= 'z' else
                         'S' if char == '\u017f' else
                         'K' if char == '\u212a' else char for char in key)
        canonical = next((field for field in _FIELDS if field.upper() == folded), None)
        if canonical is None:
            continue
        if item is not None and not isinstance(item, str):
            raise ProfileDecodeError('invalid request body')
        patch[canonical] = _replace_surrogates(item) if item is not None else None
    return patch
