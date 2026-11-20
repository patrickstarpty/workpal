"""Bounded session-authenticated binary transport."""
import re
from django.core.exceptions import DisallowedHost, RequestDataTooBig
from django.http import HttpResponse, JsonResponse
from workpal.actions import registry
from workpal.actions.http import error, invalid
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from . import artifacts


def integer(value, minimum=0, maximum=MAX_SQLITE_INTEGER):
    if not isinstance(value, str) or len(value) > 19 or not re.fullmatch(r'[0-9]+', value):
        invalid()
    number = int(value)
    if not minimum <= number <= maximum:
        invalid()
    return number


def endpoint(request, upload_id=None, artifact_id=None):
    try:
        request.get_host()
        writing = upload_id is not None
        if request.method != ('PUT' if writing else 'GET'):
            raise DomainError('method_not_allowed', 'Method not allowed.', status=405)
        if not request.user.is_authenticated or not request.user.is_active:
            raise DomainError('authentication_required', 'Login required.', status=403)
        identifier = integer(upload_id if writing else artifact_id, 1)
        allowed = {'workspace_id', 'offset'} | (set() if writing else {'length'})
        if set(request.GET) - allowed or not {'workspace_id', 'offset'} <= set(request.GET) or any(len(request.GET.getlist(k)) != 1 for k in request.GET):
            invalid()
        workspace = integer(request.GET['workspace_id'], 1)
        offset = integer(request.GET['offset'])
        length = integer(request.GET.get('length', str(artifacts.MAX_CHUNK)), 1, artifacts.MAX_CHUNK)
        declared = request.META.get('CONTENT_LENGTH', '')
        if declared:
            if len(declared) > 19 or not re.fullmatch('[0-9]+', declared):
                invalid()
            if int(declared) > artifacts.MAX_CHUNK:
                raise RequestDataTooBig()
        body = request.body
        if len(body) > artifacts.MAX_CHUNK:
            raise RequestDataTooBig()
        actor = Actor(request.user.pk, workspace, executor_id=None, session_id=request.session.session_key)
        if writing:
            if request.content_type != 'application/octet-stream' or not body:
                invalid()
            response = JsonResponse({'upload_id': identifier, 'offset': artifacts.append(actor, identifier, offset, body)})
        else:
            if body:
                invalid()
            def read():
                metadata = registry.execute(actor, ActionRequest('artifact.read', {'artifact_id':identifier}, None, None)).data
                return metadata, artifacts.read_chunk(actor, identifier, offset, length)
            metadata, chunk = atomic_write(read)
            response = HttpResponse(chunk, content_type='application/octet-stream')
            response['Content-Length'] = str(len(chunk))
            response['X-Artifact-Size'] = str(metadata['size'])
            response['X-Artifact-SHA256'] = metadata['sha256']
            response['X-Next-Offset'] = str(offset + len(chunk))
    except DomainError as exc:
        response = error(exc)
    except DisallowedHost:
        response = error(DomainError('invalid_host', 'Invalid host.'))
    except RequestDataTooBig:
        response = error(DomainError('input_too_large', 'Request is too large.', status=413))
    except Exception:
        response = error(DomainError('internal_error', 'Unable to complete action.', status=500))
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
