import json
from django.http import JsonResponse
from django.contrib.auth import login, logout, get_user_model
from django.middleware.csrf import get_token
from django.core.exceptions import DisallowedHost, RequestDataTooBig
from workpal.contracts import DomainError
from . import service

def error(exc):
    return JsonResponse({k:v for k,v in vars(exc).items() if k != "status"}, status=exc.status)

def csrf_failure(request, reason=""):
    response = error(DomainError("csrf_failed", "CSRF validation failed.", status=403))
    response["Cache-Control"] = "no-store"
    return response

def endpoint(request):
    try:
        # ALLOWED_HOSTS is enforced when get_host() is called, including reads.
        request.get_host()
        allowed_methods = {"GET"} if request.path.endswith("/csrf") else {"POST"}
        if request.method not in allowed_methods:
            raise DomainError("method_not_allowed", "Method not allowed.", status=405)
        if request.path.endswith("/csrf"):
            return JsonResponse({"csrf_token": get_token(request)})
        if request.method == "POST" and request.content_type != "application/json":
            raise DomainError("invalid_input", "Expected application/json.")
        payload = json.loads(request.body or b"{}")
        if not isinstance(payload, dict):
            raise DomainError("invalid_input", "Expected an object.")
        fields = {"username", "password"} if request.path.endswith("/login") else set()
        if set(payload) != fields:
            raise DomainError("invalid_input", "Invalid fields.")
        for key in fields:
            if not isinstance(payload[key], str) or not payload[key].strip() or len(payload[key]) > (150 if key == "username" else 4096):
                raise DomainError("invalid_input", "Invalid field.")
        if request.path.endswith("/login"):
            actor = service.authenticate(payload, request.META.get("REMOTE_ADDR", ""))
            login(request, get_user_model().objects.get(pk=actor.user_id))
            return JsonResponse({"user_id":actor.user_id})
        if not request.user.is_authenticated:
            raise DomainError("authentication_required","Login required.",status=403)
        if request.path.endswith("/logout"):
            logout(request)
            return JsonResponse({"state":"completed"})
        if request.path.endswith("/revoke-sessions"):
            from django.contrib.sessions.models import Session
            for session in Session.objects.all():
                if session.get_decoded().get("_auth_user_id") == str(request.user.pk):
                    session.delete()
            logout(request)
            return JsonResponse({"state": "completed"})
    except DomainError as exc:
        return error(exc)
    except DisallowedHost:
        return error(DomainError("invalid_host", "Invalid host."))
    except RequestDataTooBig:
        return error(DomainError("input_too_large", "Request is too large.", status=413))
    except (ValueError, KeyError, TypeError):
        return error(DomainError("invalid_input","Invalid input."))


def session_endpoint(request):
    try:
        request.get_host()
        if request.method != "GET":
            raise DomainError("method_not_allowed", "Method not allowed.", status=405)
        if request.GET:
            raise DomainError("invalid_input", "Query parameters are not allowed.")
        if not request.user.is_authenticated:
            raise DomainError("authentication_required", "Login required.", status=403)
        response = JsonResponse(service.session_context(request.user.pk))
    except DomainError as exc:
        response = error(exc)
    except DisallowedHost:
        response = error(DomainError("invalid_host", "Invalid host."))
    except Exception:
        response = error(DomainError("internal_error", "Unable to read session.", status=500))
    response["Cache-Control"] = "no-store"
    return response
