"""Session resource aliases over the shared action Interface."""
from dataclasses import asdict
from django.core.exceptions import DisallowedHost, RequestDataTooBig
from django.http import JsonResponse
from workpal.actions import registry
from workpal.actions.http import error, invalid, parse_json
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.storage import MAX_SQLITE_INTEGER


def endpoint(request, issue_id=None, delivery_id=None):
    try:
        request.get_host()
        if request.method != 'POST':
            raise DomainError('method_not_allowed', 'Method not allowed.', status=405)
        if not request.user.is_authenticated or not request.user.is_active:
            raise DomainError('authentication_required', 'Login required.', status=403)
        identifier = issue_id if issue_id is not None else delivery_id
        if type(identifier) is not int or not 1 <= identifier < MAX_SQLITE_INTEGER:
            invalid()
        payload = parse_json(request)
        submitting = issue_id is not None
        required = {'workspace_id', 'requirements_revision', 'summary'} if submitting else {'workspace_id', 'revision', 'version', 'decision'}
        allowed = required | ({'limitations', 'artifact_ids', 'evidence', 'source_refs'} if submitting else set())
        if type(payload) is not dict or not required <= set(payload) or set(payload) - allowed:
            invalid()
        workspace = payload.pop('workspace_id')
        revision = None if submitting else payload.pop('revision')
        if any(type(v) is not int or not 1 <= v <= MAX_SQLITE_INTEGER for v in ([workspace] if submitting else [workspace, revision])):
            invalid()
        key = request.headers.get('Idempotency-Key')
        confirmation = request.headers.get('X-Confirmation-ID')
        if not key or not key.strip() or (confirmation is not None and not confirmation.strip()):
            invalid()
        if submitting:
            payload['subject'] = dict(type='issue', id=str(identifier))
        else:
            payload['delivery_id'] = identifier
        actor = Actor(request.user.pk, workspace, executor_id=None, session_id=request.session.session_key)
        result = registry.execute(actor, ActionRequest('delivery.submit' if submitting else 'delivery.review', payload, revision, key, confirmation))
        response = JsonResponse(result.data if result.state == 'completed' else asdict(result))
    except DomainError as exc:
        response = error(exc)
    except DisallowedHost:
        response = error(DomainError('invalid_host', 'Invalid host.'))
    except RequestDataTooBig:
        response = error(DomainError('input_too_large', 'Request is too large.', status=413))
    except Exception:
        response = error(DomainError('internal_error', 'Unable to complete action.', status=500))
    response['Cache-Control'] = 'no-store'
    return response
