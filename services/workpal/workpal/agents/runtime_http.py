"""Bounded pairing transport. Secrets bypass Registry persistence."""
import json
from django.core.exceptions import DisallowedHost, RequestDataTooBig
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from workpal.actions.http import pairs, error, invalid
from workpal.contracts import Actor, DomainError
from . import runtime_identity as core


def _endpoint(request, workspace_id=None):
    try:
        request.get_host()
        if request.method != 'POST':
            raise DomainError('method_not_allowed', 'Method not allowed.', status=405)
        if workspace_id is not None and (not request.user.is_authenticated or not request.user.is_active):
            raise DomainError('authentication_required', 'Login required.', status=403)
        if len(request.body) > 16384:
            raise RequestDataTooBig()
        if request.GET or request.content_type != 'application/json':
            invalid()
        try:
            payload = json.loads(request.body.decode('utf-8'), object_pairs_hook=pairs,
                                 parse_constant=lambda value: invalid())
            from workpal.actions.schemas import finite_json
            finite_json(payload)
        except (ValueError, UnicodeError, RecursionError):
            invalid()
        fields = {'name'} if workspace_id is not None else {'version', 'secret'}
        if type(payload) is not dict or set(payload) != fields:
            invalid()
        if workspace_id is not None:
            core._integer(workspace_id)
            result = core.issue_pairing(Actor(request.user.pk, workspace_id, session_id=request.session.session_key), payload['name'])
        else:
            if type(payload['version']) is not int:
                invalid()
            if payload['version'] != 1:
                raise DomainError('capability_unavailable', 'Unsupported version.', status=409)
            result = core.consume_pairing(payload['secret'])
        response = JsonResponse(result)
    except DomainError as exc:
        response = error(exc)
    except DisallowedHost:
        response = error(DomainError('invalid_host', 'Invalid host.'))
    except RequestDataTooBig:
        response = error(DomainError('input_too_large', 'Request is too large.', status=413))
    except Exception:
        response = error(DomainError('internal_error', 'Unable to complete operation.', status=500))
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response

issue = _endpoint
pair = csrf_exempt(_endpoint)
