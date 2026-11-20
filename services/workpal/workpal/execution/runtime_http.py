"""Bounded bearer transport; lease decisions remain in the core module."""
import json
import re
from dataclasses import asdict
from django.core.exceptions import DisallowedHost
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from workpal.contracts import DomainError
from . import leases
from .protocol import CapabilityReport, Denied

_ERRORS = {
    'invalid_input': (400, 'Invalid request.'),
    'invalid_host': (400, 'Invalid host.'),
    'method_not_allowed': (405, 'Method not allowed.'),
    'authentication_required': (401, 'Authentication required.'),
    'permission_denied': (403, 'Permission denied.'),
    'not_found': (404, 'Not found.'),
    'capability_unavailable': (409, 'Capability unavailable.'),
    'stale_epoch': (409, 'Stale epoch.'),
    'lease_conflict': (409, 'Lease conflict.'),
    'input_too_large': (413, 'Request is too large.'),
    'storage_unavailable': (503, 'Storage unavailable.'),
    'storage_busy': (503, 'Storage busy. Retry later.'),
    'internal_error': (500, 'Unable to complete operation.'),
}


def _fail(code='invalid_input'):
    status, message = _ERRORS[code]
    raise DomainError(code, message, status=status)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            _fail()
        result[key] = value
    return result


def _unicode(value):
    if isinstance(value, str):
        value.encode('utf-8', errors='strict')
    elif isinstance(value, dict):
        for key, item in value.items():
            _unicode(key)
            _unicode(item)
    elif isinstance(value, list):
        for item in value:
            _unicode(item)


def _payload(request, fields):
    if request.GET or request.content_type != 'application/json':
        _fail()
    length = request.META.get('CONTENT_LENGTH')
    if length not in (None, ''):
        if not re.fullmatch(r'[0-9]+', length):
            _fail()
        if len(length.lstrip('0')) > 5 or int(length) > 16384:
            _fail('input_too_large')
    raw = request.read(16385)
    if len(raw) > 16384:
        _fail('input_too_large')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                           parse_constant=lambda _: _fail())
        _unicode(value)
    except (ValueError, UnicodeError, RecursionError):
        _fail()
    if type(value) is not dict or set(value) != fields:
        _fail()
    if type(value['version']) is not int:
        _fail()
    if value['version'] != 1:
        _fail('capability_unavailable')
    return value


def _endpoint(request, run_id=None):
    try:
        request.get_host()
        if request.method != 'POST':
            _fail('method_not_allowed')
        prefix = 'runtime' if run_id is None else 'task'
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        match = re.fullmatch(r'Bearer (wp_' + prefix + r'_[0-9a-f]{64})', auth)
        if not match:
            _fail('authentication_required')
        payload = _payload(request, {'version', 'capabilities'} if run_id is None else {'version', 'epoch'})
        if run_id is None:
            report = payload['capabilities']
            if type(report) is not dict or set(report) != {'provider_key', 'version', 'installed', 'authenticated', 'execution_ready'}:
                _fail()
            result = leases.claim(match[1], CapabilityReport(**report))
        else:
            result = leases.renew(match[1], run_id=run_id, epoch=payload['epoch'])
        response = JsonResponse(asdict(result), status=result.status if isinstance(result, Denied) else 200)
    except DisallowedHost:
        response = _error('invalid_host')
    except DomainError as exc:
        code = exc.code if exc.code in _ERRORS and exc.status == _ERRORS[exc.code][0] else 'internal_error'
        response = _error(code)
    except Exception:
        response = _error('internal_error')
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def _error(code):
    status, message = _ERRORS[code]
    return JsonResponse({'code': code, 'message': message}, status=status)


claim = csrf_exempt(_endpoint)
renew = csrf_exempt(_endpoint)
