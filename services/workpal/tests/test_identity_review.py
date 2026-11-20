from tests.support import identity_post
"""Regression coverage for the A1 supervisor's authorization and race findings."""
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, override_settings

from workpal.contracts import DomainError
from workpal.identity import service
from workpal.identity.models import LoginAttempt, Membership, Workspace


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class IdentityBoundaryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("owner", password="Review-password-93")
        self.admin = User.objects.create_user("admin", password="Review-password-93")
        self.member = User.objects.create_user("member", password="Review-password-93")
        self.workspace = Workspace.objects.create(name="First")
        self.other = Workspace.objects.create(name="Second")
        self.owner_link = Membership.objects.create(user=self.owner, workspace=self.workspace, role="owner")
        Membership.objects.create(user=self.admin, workspace=self.workspace, role="admin")
        self.member_link = Membership.objects.create(user=self.member, workspace=self.workspace, role="member")
        self.other_link = Membership.objects.create(user=self.member, workspace=self.other, role="owner")
        self.base = f"/api/v1/workspaces/{self.workspace.pk}"
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.owner)

    def post(self, path, payload, client=None):
        client = client or self.client
        token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        return identity_post(client, path, payload, token)

    def test_revoke_is_not_a_read_route(self):
        self.assertEqual(self.client.get(f"{self.base}/members/{self.member_link.pk}/revoke").status_code, 405)

    def test_read_rejects_untrusted_host(self):
        response = self.client.get(self.base, HTTP_HOST="untrusted.example")
        self.assertEqual(response.status_code, 400)

    def test_existing_account_conflict_has_no_account_details(self):
        response = self.post(f"{self.base}/members", {
            "username": self.member.username, "password": "Review-password-93", "role": "member",
        })
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "account_conflict")
        self.assertNotIn("username", response.json()["details"])

    def test_unprivileged_creation_does_not_validate_other_accounts(self):
        self.client.force_login(self.member)
        for username in ("owner", "new-user"):
            with self.subTest(username=username):
                result = self.post(f"{self.base}/members", {"username": username, "password": "Review-password-93", "role": "member"})
                self.assertEqual(result.status_code, 403)

    def test_admin_cannot_create_change_or_revoke_owner(self):
        self.client.force_login(self.admin)
        requests = [
            (f"{self.base}/members", {"username": "new-owner", "password": "Review-password-93", "role": "owner"}),
            (f"{self.base}/members/{self.owner_link.pk}", {"role": "member", "revision": 1}),
            (f"{self.base}/members/{self.owner_link.pk}/revoke", {"revision": 1}),
            (f"{self.base}/members/{self.member_link.pk}", {"role": "owner", "revision": 1}),
        ]
        for path, payload in requests:
            self.assertEqual(self.post(path, payload).status_code, 403)

    def test_foreign_member_id_cannot_be_changed(self):
        result = self.post(f"{self.base}/members/{self.other_link.pk}", {"role": "member", "revision": 1})
        self.assertEqual(result.status_code, 404)
        self.other_link.refresh_from_db()
        self.assertEqual(self.other_link.role, "owner")

    def test_revoking_one_membership_preserves_other_workspace_session(self):
        viewer = Client()
        viewer.force_login(self.member)
        self.assertEqual(self.post(f"{self.base}/members/{self.member_link.pk}/revoke", {"revision": 1}).status_code, 200)
        self.assertEqual(viewer.get(self.base).status_code, 404)
        self.assertEqual(viewer.get(f"/api/v1/workspaces/{self.other.pk}").status_code, 200)

    def test_all_sessions_revocation_invalidates_another_cookie(self):
        viewer = Client()
        viewer.force_login(self.owner)
        self.assertEqual(self.post("/api/v1/auth/revoke-sessions", {}).status_code, 200)
        self.assertEqual(viewer.get(self.base).status_code, 403)

    def test_payload_matrix_never_changes_workspace(self):
        for payload in (None, [], {"name": "a", "revision": True}, {"name": "", "revision": 1},
                        {"name": "x" * 201, "revision": 1}, {"name": "a", "revision": 1, "user_id": self.owner.pk}):
            with self.subTest(payload=payload):
                self.assertEqual(self.post(self.base, payload).status_code, 400)
        self.workspace.refresh_from_db()
        self.assertEqual((self.workspace.name, self.workspace.revision), ("First", 1))


class LoginConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("racing-user")

    def attempt(self, password):
        try:
            service.authenticate({"username": self.user.username, "password": password}, "127.0.0.1")
            return 200
        except DomainError as error:
            return error.status
        finally:
            connections.close_all()

    def test_concurrent_failures_are_bounded(self):
        barrier = Barrier(8)

        def password_check(**kwargs):
            barrier.wait(timeout=10)
            return None

        with patch.object(service, "django_authenticate", side_effect=password_check):
            with ThreadPoolExecutor(max_workers=8) as executor:
                outcomes = list(executor.map(self.attempt, ["bad"] * 8))
        self.assertEqual(outcomes.count(403), 5)
        self.assertEqual(outcomes.count(429), 3)
        self.assertEqual(LoginAttempt.objects.get().failures, 5)

    def test_success_does_not_erase_a_concurrent_failure(self):
        started, release = Event(), Event()

        def password_check(**kwargs):
            if kwargs["password"] == "good":
                started.set()
                if not release.wait(timeout=10):
                    raise AssertionError("Successful attempt was not released")
                return self.user
            return None

        with patch.object(service, "django_authenticate", side_effect=password_check):
            with ThreadPoolExecutor(max_workers=1) as executor:
                success = executor.submit(self.attempt, "good")
                try:
                    self.assertTrue(started.wait(timeout=10))
                    self.assertEqual(self.attempt("bad"), 403)
                finally:
                    release.set()
                self.assertEqual(success.result(timeout=10), 200)
        self.assertEqual(LoginAttempt.objects.get().failures, 1)
