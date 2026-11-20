import json
from dataclasses import replace

from django import forms
from django.test import Client, TestCase

from workpal.actions import registry
from workpal.actions.contracts import ActionSpec
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import ActionResult
from .access_support import AccessFixtures


class HTTPReviewTests(AccessFixtures, TestCase):
    def setUp(self):
        super().setUp()
        previous = registry._specs.copy()
        self.addCleanup(lambda: (registry._specs.clear(), registry._specs.update(previous)))
        registry._specs.clear()
        class Input(forms.Form):
            name = forms.CharField(max_length=30)
        registry.register(ActionSpec(
            'review.http', Input,
            {'type': 'object', 'properties': {}, 'additionalProperties': False},
            lambda *args: ActionResult('completed', [], {}), lambda *args: [],
            mutating=True,
        ))
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.csrf = self.client.get('/api/v1/auth/csrf').json()['csrf_token']

    def post(self, **changes):
        body = {'workspace_id': self.workspace.pk, 'payload': {'name': 'x'}, 'idempotency_key': 'key'}
        body.update(changes)
        return self.client.post('/api/v1/actions/review.http', json.dumps(body),
                                content_type='application/json', HTTP_X_CSRFTOKEN=self.csrf)

    def test_oversized_catalog_integer_is_client_error(self):
        response = self.client.get('/api/v1/actions', {'workspace_id': '9' * 5000})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'invalid_input')

    def test_revision_outside_storage_range_is_client_error(self):
        registry._specs['review.http'] = replace(registry._specs['review.http'], confirmation_required=True)
        self.assertEqual(self.post(expected_revision=2**63).status_code, 400)
        self.assertFalse(AuditEvent.objects.exists())
        self.assertFalse(Outbox.objects.exists())

    def test_unpaired_unicode_surrogate_is_client_error(self):
        self.assertEqual(self.post(payload={'name': '\ud800'}).status_code, 400)
        self.assertFalse(AuditEvent.objects.exists())

    def test_explicit_body_limit_and_method_checks(self):
        with self.settings(DATA_UPLOAD_MAX_MEMORY_SIZE=2 * 1024 * 1024):
            self.assertEqual(self.post(payload={'name': 'x' * (1024 * 1024)}).status_code, 413)
        response = self.client.post('/api/v1/actions', '{}', content_type='application/json',
                                    HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(response.status_code, 405)
        self.assertFalse(Outbox.objects.exists())
