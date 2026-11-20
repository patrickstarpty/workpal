from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from workpal.contracts import Actor, DomainError
from workpal.identity import service
from workpal.identity.models import Workspace, Membership
from workpal.storage import MAX_SQLITE_INTEGER


class SessionContextReview(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='context-user', password='local-test-password')
        self.manager = get_user_model().objects.create_user(username='manager')
        self.first = Workspace.objects.create(name='First')
        self.second = Workspace.objects.create(name='Second')
        self.hidden = Workspace.objects.create(name='Other users only')
        self.second_member = Membership.objects.create(user=self.user, workspace=self.second, role='member')
        self.first_member = Membership.objects.create(user=self.user, workspace=self.first, role='member')
        for workspace in (self.first, self.second, self.hidden):
            Membership.objects.create(user=self.manager, workspace=workspace, role='owner')
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.token = self.client.get('/api/v1/auth/csrf').json()['csrf_token']

    def snapshot(self):
        return {model._meta.label:list(model.objects.order_by('pk').values()) for model in apps.get_models()}

    def test_current_memberships_are_ordered_and_private_without_business_writes(self):
        before = self.snapshot()
        response = self.client.get('/api/v1/auth/session')
        expected = dict(user=dict(id=self.user.pk, username=self.user.username), workspaces=[
            dict(id=w.pk, name=w.name, revision=w.revision, role='member') for w in (self.first, self.second)])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        self.assertEqual(service.session_context(self.user.pk), expected)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(response['Cache-Control'], 'no-store')
        for secret in ('password', self.user.password, self.client.session.session_key,
                       self.manager.username, self.hidden.name, 'source_grants'):
            self.assertNotIn(secret, response.content.decode())

    def test_real_role_change_and_revocation_are_visible_to_the_existing_session(self):
        manager = Actor(self.manager.pk, self.first.pk)
        service.manage_members(manager, self.first.pk, dict(role='admin', revision=1), self.first_member.pk)
        response = self.client.get('/api/v1/auth/session')
        self.assertEqual(response.json()['workspaces'][0]['role'], 'admin')
        service.manage_members(manager, self.first.pk, dict(role=None, revision=2), self.first_member.pk, revoke=True)
        self.assertEqual([w['id'] for w in self.client.get('/api/v1/auth/session').json()['workspaces']], [self.second.pk])
        service.manage_members(Actor(self.manager.pk, self.second.pk), self.second.pk,
                               dict(role=None, revision=1), self.second_member.pk, revoke=True)
        self.assertEqual(self.client.get('/api/v1/auth/session').json(),
                         dict(user=dict(id=self.user.pk, username=self.user.username), workspaces=[]))

    def test_method_query_host_anonymous_and_inactive_requests_are_not_cacheable(self):
        before = self.snapshot()
        for response, expected in (
            (self.client.get('/api/v1/auth/session?user_id=' + str(self.manager.pk)), 400),
            (self.client.get('/api/v1/auth/session?workspace_id=1'), 400),
            (self.client.get('/api/v1/auth/session', HTTP_HOST='outside.invalid'), 400),
            (self.client.post('/api/v1/auth/session', {}, content_type='application/json', HTTP_X_CSRFTOKEN=self.token), 405),
            (Client().get('/api/v1/auth/session'), 403),
        ):
            self.assertEqual(response.status_code, expected, response.content)
            self.assertIn('no-store', response.get('Cache-Control', ''))
        self.assertEqual(self.snapshot(), before)
        self.user.is_active = False
        self.user.save()
        response = self.client.get('/api/v1/auth/session')
        self.assertEqual(response.status_code, 403)
        self.assertIn('no-store', response['Cache-Control'])
        with self.assertRaises(DomainError) as caught:
            service.session_context(self.user.pk)
        self.assertEqual(caught.exception.status, 403)

    def test_direct_interface_rejects_noncanonical_user_ids(self):
        for value in (True, False, None, str(self.user.pk), 0, -1, MAX_SQLITE_INTEGER + 1):
            with self.subTest(value=value):
                with self.assertRaises(DomainError) as caught:
                    service.session_context(value)
                self.assertEqual(caught.exception.status, 400)

    def test_unexpected_context_failure_is_sanitized_and_not_cached(self):
        before = self.snapshot()
        self.client.raise_request_exception = False
        with patch.object(service, 'session_context', side_effect=RuntimeError('private internal failure')):
            response = self.client.get('/api/v1/auth/session')
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b'private internal failure', response.content)
        self.assertEqual(response.get('Cache-Control'), 'no-store')
        self.assertEqual(response.json()['code'], 'internal_error')
        self.assertEqual(self.snapshot(), before)
