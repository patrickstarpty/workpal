"""Session-authenticated JSON transport for the action registry."""
import json
import re
from dataclasses import asdict
from django.core.exceptions import DisallowedHost, RequestDataTooBig
from django.http import JsonResponse
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.storage import MAX_SQLITE_INTEGER
from . import registry


def error(exc):
    return JsonResponse({k: v for k, v in vars(exc).items() if k != 'status'}, status=exc.status)


def invalid():
    raise DomainError('invalid_input', 'Invalid action request.')


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            invalid()
        result[key] = value
    return result


def endpoint(request, action_id=None):
    try:
        request.get_host()
        if request.method != ('POST' if action_id is not None else 'GET'):
            raise DomainError('method_not_allowed', 'Method not allowed.', status=405)
        if not request.user.is_authenticated or not request.user.is_active:
            raise DomainError('authentication_required', 'Login required.', status=403)
        if action_id is None:
            values = request.GET.getlist('workspace_id')
            if set(request.GET) != {'workspace_id'} or len(values) != 1 or len(values[0]) > 19 or not re.fullmatch(r'[1-9][0-9]*', values[0]):
                invalid()
            workspace_id = int(values[0])
            if workspace_id > MAX_SQLITE_INTEGER:
                invalid()
        else:
            if request.GET or request.content_type != 'application/json':
                invalid()
            envelope = parse_json(request)
            if type(envelope) is not dict or set(envelope) - {'workspace_id','payload','expected_revision','idempotency_key','confirmation_id'}:
                invalid()
            workspace_id = envelope.get('workspace_id')
            if type(workspace_id) is not int or not 1 <= workspace_id <= MAX_SQLITE_INTEGER or type(envelope.get('payload')) is not dict:
                invalid()
            revision = envelope.get('expected_revision')
            if revision is not None and type(revision) is not int:
                invalid()
            for field in ('idempotency_key','confirmation_id'):
                value = envelope.get(field)
                if value is not None and (type(value) is not str or not value.strip()):
                    invalid()
        actor = Actor(request.user.pk, workspace_id, executor_id=None, session_id=request.session.session_key)
        if action_id is None:
            return JsonResponse({'actions': registry.catalog(actor)})
        result = registry.execute(actor, ActionRequest(action_id, envelope['payload'], revision, envelope.get('idempotency_key'), envelope.get('confirmation_id')))
        return JsonResponse(asdict(result))
    except DomainError as exc:
        return error(exc)
    except DisallowedHost:
        return error(DomainError('invalid_host', 'Invalid host.'))
    except RequestDataTooBig:
        return error(DomainError('input_too_large', 'Request is too large.', status=413))
    except Exception:
        return error(DomainError('internal_error', 'Unable to complete action.', status=500))


def parse_json(request):
    if request.GET or request.content_type != 'application/json':
        invalid()
    try:
        body = request.body
        if len(body) > 1024 * 1024:
            raise RequestDataTooBig()
        value = json.loads(body, object_pairs_hook=pairs, parse_constant=lambda value: invalid())
        from .schemas import finite_json
        finite_json(value)
        return value
    except (ValueError, UnicodeError, RecursionError):
        invalid()


def resource_endpoint(request, workspace_id, membership_id=None):
    try:
        request.get_host()
        revoke = request.path.endswith('/revoke')
        if request.method not in ({'POST'} if membership_id is not None else {'GET', 'POST'}):
            raise DomainError('method_not_allowed', 'Method not allowed.', status=405)
        if not request.user.is_authenticated or not request.user.is_active:
            raise DomainError('authentication_required', 'Login required.', status=403)
        if any(type(value) is not int or not 1 <= value <= MAX_SQLITE_INTEGER
               for value in (workspace_id, membership_id) if value is not None):
            invalid()
        members = '/members' in request.path
        action = ('member.revoke' if revoke else 'member.set_role' if membership_id is not None
                  else 'member.create' if members else 'workspace.rename') if request.method == 'POST' else ('member.list' if members else 'workspace.read')
        payload, revision, key, confirmation = {}, None, None, None
        if request.method == 'POST':
            payload = parse_json(request)
            fields = {'workspace.rename': {'name', 'revision'}, 'member.create': {'username', 'password', 'role'},
                      'member.set_role': {'role', 'revision'}, 'member.revoke': {'revision'}}[action]
            if type(payload) is not dict or set(payload) != fields:
                invalid()
            revision = payload.pop('revision', None)
            if 'revision' in fields and (type(revision) is not int or not 1 <= revision <= MAX_SQLITE_INTEGER):
                invalid()
            key = request.headers.get('Idempotency-Key')
            confirmation = request.headers.get('X-Confirmation-ID')
            if not key or not key.strip() or (confirmation is not None and not confirmation.strip()):
                invalid()
            if membership_id is not None:
                payload['membership_id'] = membership_id
        elif request.GET or request.body:
            invalid()
        actor = Actor(request.user.pk, workspace_id, executor_id=None, session_id=request.session.session_key)
        result = registry.execute(actor, ActionRequest(action, payload, revision, key, confirmation))
        return JsonResponse(asdict(result) if result.state != 'completed' else
                            {'state': 'completed'} if revoke else result.data)
    except DomainError as exc:
        return error(exc)
    except DisallowedHost:
        return error(DomainError('invalid_host', 'Invalid host.'))
    except RequestDataTooBig:
        return error(DomainError('input_too_large', 'Request is too large.', status=413))
    except Exception:
        return error(DomainError('internal_error', 'Unable to complete action.', status=500))
