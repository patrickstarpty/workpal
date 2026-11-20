import json
from dataclasses import replace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client

from workpal.actions import registry
from workpal.actions.models import Confirmation, IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.identity.models import Workspace, Membership
from workpal.contracts import Actor
from .support import WorkpalCase


class IdentityAliasReviewTests(WorkpalCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('review-owner')
        self.workspace = Workspace.objects.create(name='Original')
        self.member = Membership.objects.create(user=self.user, workspace=self.workspace, role='owner')
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.csrf = self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        self.base = f'/api/v1/workspaces/{self.workspace.pk}'

    def raw_post(self, path, body, **headers):
        headers.setdefault('HTTP_X_CSRFTOKEN', self.csrf)
        return self.client.post(path, body, content_type='application/json', **headers)

    def alias(self, suffix, payload, key='key', token=None, **headers):
        headers.setdefault('HTTP_IDEMPOTENCY_KEY', key)
        if token is not None:
            headers['HTTP_X_CONFIRMATION_ID'] = token
        return self.raw_post(self.base + suffix, json.dumps(payload), **headers)

    def action(self, name, payload, revision=None, key='key', token=None, **headers):
        body = {'workspace_id': self.workspace.pk, 'payload': payload,
                'expected_revision': revision, 'idempotency_key': key, 'confirmation_id': token}
        return self.raw_post('/api/v1/actions/' + name, json.dumps(body), **headers)

    def test_rename_replays_across_routes_once(self):
        first = self.alias('', {'name': 'Changed', 'revision': 1})
        self.assertEqual(first.status_code, 200, first.content)
        replay = self.action('workspace.rename', {'name': 'Changed'}, 1)
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertEqual(first.json(), replay.json()['data'])
        self.assertEqual(self.alias('', {'name': 'Changed', 'revision': 1}).json(), first.json())
        self.workspace.refresh_from_db()
        self.assertEqual((self.workspace.name, self.workspace.revision), ('Changed', 2))
        self.assertEqual((AuditEvent.objects.count(), Outbox.objects.count(), IdempotencyResult.objects.count()), (1, 1, 1))
        a = self.alias('', {'name': 'Different', 'revision': 1})
        b = self.action('workspace.rename', {'name': 'Different'}, 1)
        self.assertEqual((a.status_code, b.status_code), (409, 409))
        self.assertEqual(a.json()['code'], b.json()['code'])

    def test_create_confirmation_crosses_routes_and_keeps_secrets_out(self):
        secret = 'Alias-Review-Password-492!'
        payload = {'username': 'created', 'password': secret, 'role': 'member'}
        pending = self.alias('/members', payload)
        self.assertEqual(pending.json()['state'], 'waiting_confirmation')
        self.assertEqual(Confirmation.objects.count(), 1)
        self.assertFalse(get_user_model().objects.filter(username='created').exists())
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(Outbox.objects.exists())
        token = pending.json()['data']['confirmation_id']
        done = self.action('member.create', payload, token=token)
        self.assertEqual(done.status_code, 200, done.content)
        self.assertEqual(self.alias('/members', payload, token=token).json(), done.json()['data'])
        self.assertTrue(get_user_model().objects.get(username='created').check_password(secret))
        self.assertEqual(Membership.objects.filter(workspace=self.workspace).count(), 2)
        self.assertEqual((AuditEvent.objects.count(), Outbox.objects.count(), IdempotencyResult.objects.count()), (1, 1, 1))
        self.assertEqual(AuditEvent.objects.get().fields, {'username': 'created', 'role': 'member'})
        for model in (Confirmation, IdempotencyResult, AuditEvent, Outbox):
            self.assertNotIn(secret, json.dumps(list(model.objects.values()), default=str))
        self.assertNotIn(secret, pending.content.decode() + done.content.decode())

    def test_confirmation_prepared_by_generic_route_consumed_by_alias(self):
        payload = {'username': 'reverse', 'password': 'Alias-Review-Password-492!', 'role': 'member'}
        pending = self.action('member.create', payload)
        token = pending.json()['data']['confirmation_id']
        done = self.alias('/members', payload, token=token)
        self.assertEqual(done.status_code, 200, done.content)
        replay = self.action('member.create', payload, token=token)
        self.assertEqual(replay.json()['data'], done.json())
        self.assertEqual((AuditEvent.objects.count(), Outbox.objects.count()), (1, 1))

    def test_role_change_and_revoke_share_confirmations_and_results(self):
        user = get_user_model().objects.create_user('target')
        target = Membership.objects.create(user=user, workspace=self.workspace, role='member')
        payload = {'membership_id': target.pk, 'role': 'admin'}
        pending = self.action('member.set_role', payload, 1, key='role')
        target.refresh_from_db()
        self.assertEqual(target.role, 'member')
        self.assertFalse(Outbox.objects.exists())
        token = pending.json()['data']['confirmation_id']
        done = self.alias(f'/members/{target.pk}', {'role': 'admin', 'revision': 1}, key='role', token=token)
        self.assertEqual(done.status_code, 200, done.content)
        self.assertEqual(self.action('member.set_role', payload, 1, key='role', token=token).json()['data'], done.json())
        target.refresh_from_db()
        self.assertEqual((target.role, target.revision), ('admin', 2))
        pending = self.alias(f'/members/{target.pk}/revoke', {'revision': 2}, key='revoke')
        self.assertTrue(Membership.objects.filter(pk=target.pk).exists())
        token = pending.json()['data']['confirmation_id']
        done = self.action('member.revoke', {'membership_id': target.pk}, 2, key='revoke', token=token)
        self.assertEqual(done.status_code, 200, done.content)
        self.assertEqual(self.alias(f'/members/{target.pk}/revoke', {'revision': 2}, key='revoke', token=token).json(), {'state': 'completed'})
        self.assertFalse(Membership.objects.filter(pk=target.pk).exists())
        self.assertEqual((AuditEvent.objects.count(), Outbox.objects.count()), (2, 2))

    def test_read_aliases_use_audit_without_outbox(self):
        for suffix, action in (('', 'workspace.read'), ('/members', 'member.list')):
            direct = self.act(Actor(self.user.pk, self.workspace.pk), action, {})
            a = self.client.get(self.base + suffix)
            b = self.action(action, {}, key=None)
            self.assertEqual(a.status_code, 200, a.content)
            self.assertEqual(a.json(), b.json()['data'])
            self.assertEqual(a.json(), direct.data)
            self.assertEqual(AuditEvent.objects.filter(action_id=action).count(), 3)
        self.assertFalse(Outbox.objects.exists())

    def test_permissions_hosts_and_csrf_match(self):
        calls = (
            lambda **headers: self.alias('', {'name': 'Changed', 'revision': 1}, **headers),
            lambda **headers: self.action('workspace.rename', {'name': 'Changed'}, 1, **headers),
        )
        for call in calls:
            self.assertEqual(call(HTTP_X_CSRFTOKEN='').status_code, 403)
            response = call(HTTP_HOST='untrusted.example')
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()['code'], 'invalid_host')
        self.member.role = 'member'
        self.member.save()
        for call in calls:
            response = call()
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['code'], 'permission_denied')
        self.member.delete()
        for call in calls:
            self.assertEqual(call().status_code, 404)
        self.client.logout()
        self.csrf = self.client.get('/api/v1/auth/csrf').json()['csrf_token']
        for call in calls:
            response = call()
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['code'], 'authentication_required')
        self.assertFalse(AuditEvent.objects.exists())

    def test_alias_invalid_input_has_no_business_effects(self):
        bodies = [None, [], {}, {'name': 'x'}, {'name': 'x', 'revision': True},
                  {'name': 'x', 'revision': 0}, {'name': 'x', 'revision': 2**63},
                  {'name': 'x', 'revision': 1, 'user_id': self.user.pk},
                  {'name': 'x', 'revision': 1, 'workspace_id': self.workspace.pk},
                  {'name': '\ud800', 'revision': 1}]
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(self.alias('', body).status_code, 400)
        for raw in ('{"name":"x","name":"y","revision":1}', '{"name":NaN,"revision":1}', '{'):
            self.assertEqual(self.raw_post(self.base, raw, HTTP_IDEMPOTENCY_KEY='key').status_code, 400)
        for headers in ({'HTTP_IDEMPOTENCY_KEY': ''}, {'HTTP_IDEMPOTENCY_KEY': 'x' * 201}, {'HTTP_X_CONFIRMATION_ID': ''}):
            self.assertEqual(self.alias('', {'name': 'x', 'revision': 1}, **headers).status_code, 400)
        for path in ('/api/v1/workspaces/0', '/api/v1/workspaces/' + str(2**63)):
            self.assertEqual(self.client.get(path).status_code, 400)
        self.assertEqual(self.client.get(self.base, {'user_id': self.user.pk}).status_code, 400)
        self.assertEqual(self.client.get(self.base + f'/members/{self.member.pk}/revoke').status_code, 405)
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=2 * 1024 * 1024):
            self.assertEqual(self.alias('', {'name': 'x' * (1024 * 1024), 'revision': 1}).status_code, 413)
        self.workspace.refresh_from_db()
        self.assertEqual((self.workspace.name, self.workspace.revision), ('Original', 1))
        self.assertFalse(Outbox.objects.exists())

    def test_internal_failure_is_rolled_back_and_hidden_on_both_routes(self):
        def fail(*args):
            Workspace.objects.filter(pk=self.workspace.pk).update(name='partial')
            raise RuntimeError('sensitive SQL password detail')
        spec = replace(registry._specs['workspace.rename'], handler=fail)
        with patch.dict(registry._specs, {'workspace.rename': spec}):
            responses = (self.alias('', {'name': 'x', 'revision': 1}),
                         self.action('workspace.rename', {'name': 'x'}, 1))
        for response in responses:
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json()['code'], 'internal_error')
            self.assertNotIn('sensitive', response.content.decode())
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.name, 'Original')
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(Outbox.objects.exists())
