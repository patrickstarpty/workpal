"""Issue resource transport; policy and transactions belong to the Registry."""
from dataclasses import asdict
from django.core.exceptions import DisallowedHost, RequestDataTooBig
from django.http import JsonResponse
from workpal.actions import registry
from workpal.actions.http import parse_json, error, invalid
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.storage import MAX_SQLITE_INTEGER


def positive(value):
    if type(value) is not int or not 1 <= value <= MAX_SQLITE_INTEGER:
        invalid()
    return value


def endpoint(request, workspace_id=None, issue_id=None):
    try:
        request.get_host()
        if request.method != 'POST':
            raise DomainError('method_not_allowed', 'Method not allowed.', status=405)
        if not request.user.is_authenticated or not request.user.is_active:
            raise DomainError('authentication_required', 'Login required.', status=403)
        payload = parse_json(request)
        if type(payload) is not dict:
            invalid()
        revision = None
        if issue_id is None:
            positive(workspace_id)
            if 'workspace_id' in payload:
                invalid()
            action = 'issue.create'
        else:
            positive(issue_id)
            if 'issue_id' in payload:
                invalid()
            workspace_id = positive(payload.pop('workspace_id', None))
            revision = positive(payload.pop('revision', None))
            payload['issue_id'] = issue_id
            action = 'issue.transition'
        key = request.headers.get('Idempotency-Key')
        confirmation = request.headers.get('X-Confirmation-ID')
        if not key or not key.strip() or (confirmation is not None and not confirmation.strip()):
            invalid()
        actor = Actor(request.user.pk, workspace_id, executor_id=None, session_id=request.session.session_key)
        result = registry.execute(actor, ActionRequest(action, payload, revision, key, confirmation))
        return JsonResponse(result.data if result.state == 'completed' else asdict(result))
    except DomainError as exc:
        return error(exc)
    except DisallowedHost:
        return error(DomainError('invalid_host', 'Invalid host.'))
    except RequestDataTooBig:
        return error(DomainError('input_too_large', 'Request is too large.', status=413))
    except Exception:
        return error(DomainError('internal_error', 'Unable to complete action.', status=500))
