"""Bounded, side-effect-free uploaded excerpt normalization."""
import hashlib
import json
import math
import re

from workpal.contracts import DomainError

_LIMIT = 2097152


def _fail(code='invalid_upload', status=400):
    raise DomainError(code, 'Upload normalization rejected.', status=status) from None


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _unicode(value):
    value.encode('utf-8')


def _policy(policy):
    try:
        if type(policy) is not dict or set(policy) != {'version', 'allow_text', 'allow_fields', 'redact_literals'}:
            raise ValueError
        if type(policy['version']) is not int or policy['version'] != 1 or type(policy['allow_text']) is not bool:
            raise ValueError
        result = dict(version=1, allow_text=policy['allow_text'])
        for key, maximum in [('allow_fields', 128), ('redact_literals', 256)]:
            values = policy[key]
            if type(values) is not list or len(values) > 100:
                raise ValueError
            for value in values:
                if type(value) is not str or not 1 <= len(value) <= maximum:
                    raise ValueError
                _unicode(value)
            if len(set(values)) != len(values):
                raise ValueError
            result[key] = sorted(values)
        if any(literal in field for field in result['allow_fields'] for literal in result['redact_literals']):
            raise ValueError
        return result
    except (ValueError, TypeError, UnicodeError):
        _fail('invalid_redaction_policy')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _unicode(key)
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _constant(value):
    raise ValueError


def _validate_json_values(value):
    # Dropping a field does not make malformed JSON scalar values valid.
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is dict:
            pending.extend(item.values())
        elif type(item) is list:
            pending.extend(item)
        elif type(item) is str:
            _unicode(item)
        elif type(item) is float and not math.isfinite(item):
            raise ValueError


def normalize_upload(content: bytes, *, format: str, policy: dict) -> dict:
    """Return a bounded copy and factual hashes/counts; never persist raw bytes."""
    if type(content) is not bytes:
        _fail()
    if len(content) > _LIMIT:
        _fail('upload_too_large', 413)
    if type(format) is not str or format not in ('text', 'jsonl'):
        _fail()
    clean_policy = _policy(policy)
    if format == 'text' and not clean_policy['allow_text']:
        _fail('text_upload_not_allowed', 403)
    try:
        decoded = content.decode('utf-8-sig')
    except UnicodeError:
        _fail()
    records = [(number, line[:-1] if line.endswith('\r') else line)
               for number, line in enumerate(decoded.split('\n'), 1) if line.strip()]
    literals = sorted(clean_policy['redact_literals'], key=lambda value: (-len(value), value))
    pattern = re.compile('|'.join(re.escape(value) for value in literals)) if literals else None
    redactions = 0

    def mask(value):
        nonlocal redactions
        if pattern is None:
            return value
        result, count = pattern.subn(lambda match: '[REDACTED]', value)
        redactions += count
        return result

    output, omitted, output_size = [], 0, 0
    for _, line in records[:1000]:
        try:
            if format == 'text':
                normalized = mask(line)
            else:
                obj = json.loads(line, object_pairs_hook=_pairs, parse_constant=_constant)
                _validate_json_values(obj)
                if type(obj) is not dict:
                    raise ValueError
                selected = {}
                for key, value in obj.items():
                    if key not in clean_policy['allow_fields']:
                        omitted += 1
                        continue
                    if type(value) not in (type(None), bool, int, float, str):
                        raise ValueError
                    if type(value) is float and not math.isfinite(value):
                        raise ValueError
                    if type(value) is str:
                        _unicode(value)
                        value = mask(value)
                    selected[key] = value
                normalized = _canonical(selected)
            size = len(normalized.encode('utf-8'))
        except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
            _fail()
        output_size += size + bool(output)
        if output_size > _LIMIT:
            _fail('normalized_upload_too_large', 413)
        output.append(normalized)
    text = '\n'.join(output)
    digest = lambda value: hashlib.sha256(value).hexdigest()
    truncated = len(records) > 1000
    return dict(origin='user_upload', coverage='uploaded_excerpt', format=format,
                status='truncated' if truncated else ('ok' if records else 'no_data'),
                content=text, raw_sha256=digest(content), content_sha256=digest(text.encode('utf-8')),
                policy_sha256=digest(_canonical(clean_policy).encode('utf-8')),
                raw_bytes=len(content), content_bytes=output_size, total_records=len(records),
                included_records=len(output), included_line_numbers=[n for n, _ in records[:1000]],
                truncated=truncated, redaction_count=redactions, omitted_fields=omitted)
