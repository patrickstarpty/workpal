from django.contrib.auth import authenticate as django_authenticate, get_user_model
from django.db.models import F
from workpal.contracts import Actor, DomainError
from workpal.storage import atomic_write, MAX_SQLITE_INTEGER
from .models import Membership, Workspace

def authenticate(credentials, remote_addr=""):
    import hashlib
    from datetime import timedelta
    from django.utils import timezone
    from .models import LoginAttempt
    key = hashlib.sha256((credentials["username"] + "\0" + remote_addr).encode()).hexdigest()
    def current_attempt():
        now = timezone.now()
        row, _ = LoginAttempt.objects.get_or_create(key=key)
        if row.updated <= now - timedelta(minutes=5):
            row.failures = 0
            row.save()
        return row

    def admit():
        row = current_attempt()
        if row.failures >= 5:
            raise DomainError("rate_limited", "Try again later.", status=429)
        return row.pk, row.updated, row.failures

    # Password hashing happens outside the SQLite write transaction. In-flight
    # requests are not failures; finalization caps concurrent failed attempts.
    admitted_id, admitted_at, admitted_failures = atomic_write(admit)
    user = django_authenticate(username=credentials["username"], password=credentials["password"])
    if user is None:
        def record_failure():
            row = current_attempt()
            if row.failures >= 5:
                return False
            row.failures += 1
            row.save()
            return True

        if not atomic_write(record_failure):
            raise DomainError("rate_limited", "Try again later.", status=429)
        raise DomainError("invalid_credentials", "Invalid credentials.", status=403)
    # Clear only the failures this successful attempt observed. A failure
    # committed while the password was checked must not disappear.
    atomic_write(lambda: LoginAttempt.objects.filter(
        pk=admitted_id, updated=admitted_at, failures=admitted_failures
    ).delete())
    return Actor(user.pk, None)

def require_member(actor, workspace_id):
    member = Membership.objects.filter(user_id=actor.user_id, user__is_active=True, workspace_id=workspace_id).first()
    if member is None:
        raise DomainError("not_found", "Workspace not found.", status=404)
    return member

def rename_workspace(actor, workspace_id, name, revision):
    def write():
        member = require_member(actor, workspace_id)
        if member.role not in ("owner", "admin"):
            raise DomainError("permission_denied", "Permission denied.", status=403)
        if not Workspace.objects.filter(pk=workspace_id, revision=revision).update(name=name, revision=F("revision")+1):
            raise DomainError("revision_conflict", "Reload and retry.", status=409)
        return Workspace.objects.get(pk=workspace_id)
    return atomic_write(write)

def manage_members(actor, workspace_id, payload=None, membership_id=None, revoke=False):
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    from django.db import IntegrityError
    User = get_user_model()
    manager = require_member(actor, workspace_id)
    if manager.role not in ("owner", "admin"):
        raise DomainError("permission_denied", "Permission denied.", status=403)
    if payload is not None and payload.get("role") == "owner" and manager.role != "owner":
        raise DomainError("permission_denied", "Permission denied.", status=403)
    candidate = None
    if payload is not None and membership_id is None:
        candidate = User(username=payload["username"])
        try:
            candidate.full_clean(exclude=["password"], validate_unique=False)
            validate_password(payload["password"], candidate)
        except ValidationError:
            raise DomainError("invalid_input", "Invalid account details.")
        candidate.set_password(payload["password"])
    def write():
        manager = require_member(actor, workspace_id)
        if manager.role not in ("owner", "admin"):
            raise DomainError("permission_denied", "Permission denied.", status=403)
        if payload is None:
            return list(Membership.objects.filter(workspace_id=workspace_id).select_related("user"))
        role = payload.get("role")
        if membership_id is None:
            if role == "owner" and manager.role != "owner":
                raise DomainError("permission_denied", "Permission denied.", status=403)
            candidate.save()
            return Membership.objects.create(user=candidate, workspace_id=workspace_id, role=role)
        target = Membership.objects.filter(pk=membership_id, workspace_id=workspace_id).first()
        if target is None:
            raise DomainError("not_found", "Member not found.", status=404)
        if target.revision != payload["revision"]:
            raise DomainError("revision_conflict", "Reload and retry.", status=409)
        if manager.role == "admin" and (target.role == "owner" or role == "owner"):
            raise DomainError("permission_denied", "Permission denied.", status=403)
        if target.role == "owner" and (revoke or role != "owner") and Membership.objects.filter(workspace_id=workspace_id, role="owner").count() == 1:
            raise DomainError("last_owner", "Keep at least one owner.", status=409)
        if revoke:
            target.delete()
            return None
        target.role = role
        target.revision += 1
        target.save()
        return target
    try:
        return atomic_write(write)
    except IntegrityError:
        raise DomainError("account_conflict", "Account unavailable.", status=409)

def create_member(actor, workspace_id, username, password, role="member"):
    return manage_members(actor, workspace_id, dict(username=username, password=password, role=role))

def session_context(user_id):
    if type(user_id) is not int or not 1 <= user_id <= MAX_SQLITE_INTEGER:
        raise DomainError('invalid_input', 'Invalid user ID.')
    user = get_user_model().objects.filter(pk=user_id, is_active=True).only('id', 'username').first()
    if user is None:
        raise DomainError('authentication_required', 'Login required.', status=403)
    return {'user': {'id': user.pk, 'username': user.username}, 'workspaces': [
        {'id': m.workspace_id, 'name': m.workspace.name, 'revision': m.workspace.revision, 'role': m.role}
        for m in Membership.objects.filter(user=user).select_related('workspace').order_by('workspace_id')
    ]}
