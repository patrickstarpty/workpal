import json
from unittest.mock import patch
from django.test import TestCase, Client
from tests import test_runtime_http as fixtures
from workpal.actions import registry
from workpal.actions.models import IdempotencyResult
from workpal.agents import runtime_identity as core
from workpal.agents.models import Runtime, RuntimePairing
from workpal.access.models import RegisteredObject, SourceLink
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import DomainError


class RuntimeHTTPReviewTests(TestCase):
    setUp = fixtures.RuntimeHTTPTests.setUp
    post = fixtures.RuntimeHTTPTests.post
    paired = fixtures.RuntimeHTTPTests.paired

    def test_real_csrf_session_and_anonymous_pair_management_roundtrip(self):
        client = Client(enforce_csrf_checks=True)
        token = client.get('/api/v1/auth/csrf').json()['csrf_token']
        login = client.post('/api/v1/auth/login', dict(username='http-owner', password='pass'),
            content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login.status_code, 200)
        token = client.get('/api/v1/auth/csrf').json()['csrf_token']
        issued_response = client.post(self.url, dict(name='Review runtime'),
            content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(issued_response.status_code, 200)
        issued = issued_response.json()
        anonymous = Client(enforce_csrf_checks=True)
        response = anonymous.post('/api/runtime/v1/pair', dict(version=1, secret=issued['secret']),
            content_type='application/json')
        self.assertEqual(response.status_code, 200)
        paired = response.json()
        def action(name, payload, **extra):
            return client.post('/api/v1/actions/' + name, dict(
                workspace_id=self.workspace.pk, payload=payload, **extra),
                content_type='application/json', HTTP_X_CSRFTOKEN=token)
        metadata = action('runtime.pairing.read', dict(pairing_id=issued['pairing_id']))
        self.assertEqual(metadata.status_code, 200)
        self.assertEqual(metadata.json()['data']['runtime_id'], paired['runtime_id'])
        read = action('runtime.read', dict(runtime_id=paired['runtime_id']))
        self.assertEqual(read.status_code, 200)
        revoke = action('runtime.revoke', dict(runtime_id=paired['runtime_id']),
            expected_revision=1, idempotency_key='http-revoke')
        self.assertEqual(revoke.status_code, 200)
        self.assertTrue(revoke.json()['data']['revoked'])
        with self.assertRaises(DomainError) as caught:
            core.authenticate_runtime(paired['runtime_token'])
        self.assertEqual(caught.exception.status, 401)
        for reply in (issued_response, response, metadata, read, revoke):
            self.assertEqual(reply['Cache-Control'], 'no-store')
            self.assertEqual(reply['X-Content-Type-Options'], 'nosniff')
        saved = str(list(AuditEvent.objects.values())) + str(list(Outbox.objects.values())) + str(list(IdempotencyResult.objects.values()))
        for secret in (issued['secret'], paired['runtime_token']):
            self.assertNotIn(secret, saved)

    def test_exact_sixteen_kib_and_one_byte_over(self):
        body = json.dumps(dict(name='Exact boundary')).encode()
        body += b' ' * (16384 - len(body))
        response = self.client.post(self.url, body, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        before = RuntimePairing.objects.count()
        denied = self.client.post(self.url, body + b' ', content_type='application/json')
        self.assertEqual(denied.status_code, 413)
        self.assertEqual(RuntimePairing.objects.count(), before)

    def test_registry_revoke_actual_audit_failure_restores_all_rows(self):
        _, paired = self.paired()
        models = (Runtime, RuntimePairing, RegisteredObject, SourceLink,
                  AuditEvent, Outbox, IdempotencyResult)
        def snapshot():
            return {model._meta.label: list(model.objects.order_by('pk').values()) for model in models}
        def revoke():
            return self.post('/api/v1/actions/runtime.revoke', dict(workspace_id=self.workspace.pk,
                payload=dict(runtime_id=paired['runtime_id']), expected_revision=1,
                idempotency_key='rollback-revoke'))
        before = snapshot()
        original = registry.record
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise DomainError('storage_unavailable', 'Unavailable.', status=503)
        with patch.object(registry, 'record', side_effect=fail):
            self.assertEqual(revoke().status_code, 503)
        self.assertEqual(snapshot(), before)
        self.assertEqual(core.authenticate_runtime(paired['runtime_token']).runtime_id, paired['runtime_id'])
        result = revoke()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(revoke().json(), result.json())
        self.assertEqual(AuditEvent.objects.filter(action_id='runtime.revoke').count(), 1)
        self.assertEqual(Outbox.objects.filter(action_id='runtime.revoke').count(), 1)
        self.assertEqual(IdempotencyResult.objects.filter(action_id='runtime.revoke').count(), 1)
