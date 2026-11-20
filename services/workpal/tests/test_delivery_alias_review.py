from unittest.mock import patch

from django.test import Client
from tests.support import WorkpalCase
from tests.test_review_validation import ReviewFixtures
from workpal.actions import registry
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.contracts import DomainError
from workpal.delivery.models import Review, DeliveryCurrent
from workpal.storage import MAX_SQLITE_INTEGER


class DeliveryAliasReview(ReviewFixtures, WorkpalCase):
    def setUp(self):
        super().setUp()
        self.target = self.ready()
        self.url = f'/api/v1/deliveries/{self.target["id"]}/reviews'
        self.body = dict(workspace_id=self.workspace.pk, revision=2, version=self.target['number'],
                         decision=dict(outcome='approve', reason='Human review.'))
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.token = self.client.get('/api/v1/auth/csrf').json()['csrf_token']

    def post(self, body=None, path=None, key='review-http', **headers):
        headers.setdefault('HTTP_X_CSRFTOKEN', self.token)
        return self.client.post(path or self.url, self.body if body is None else body,
            content_type='application/json', HTTP_IDEMPOTENCY_KEY=key, **headers)

    def test_review_closed_fields_and_integer_contract_preserve_all_state(self):
        before = self.snapshot()
        for field in ('delivery_id', 'subject', 'user_id', 'executor_id', 'approved', 'unknown'):
            self.assertEqual(self.post(dict(self.body, **{field: 1})).status_code, 400)
        for field in ('workspace_id', 'revision', 'version'):
            for value in (True, False, None, '1', 0, -1, MAX_SQLITE_INTEGER + 1):
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.post(dict(self.body, **{field: value})).status_code, 400)
        for decision in (None, [], dict(self.body['decision'], approved=True),
                         dict(outcome='approve', reason=' '), dict(outcome='passed', reason='Claim')):
            self.assertEqual(self.post(dict(self.body, decision=decision)).status_code, 400)
        for identifier in (0, MAX_SQLITE_INTEGER, MAX_SQLITE_INTEGER + 1):
            self.assertEqual(self.post(path=f'/api/v1/deliveries/{identifier}/reviews').status_code, 400)
        self.assertEqual(self.snapshot(), before)

    def test_review_host_csrf_and_transport_errors_have_a_real_positive_control(self):
        before = self.snapshot()
        for response, status in (
            (self.client.get(self.url), 405),
            (self.post(HTTP_HOST='untrusted.invalid'), 400),
            (self.post(HTTP_X_CSRFTOKEN=''), 403),
            (self.post(path=self.url + '?revision=2'), 400),
            (self.post(body='[]'), 400),
            (self.post(body='{"version":1,"version":2}'), 400),
            (self.post(body=' ' * (1024 * 1024 + 1)), 413),
        ):
            self.assertEqual(response.status_code, status, response.content)
            self.assertIn('no-store', response.get('Cache-Control', ''))
        self.assertEqual(self.snapshot(), before)
        response = self.post()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response.json()['actor_user_id'], self.user.pk)

    def test_review_audit_failure_rolls_back_revision_sources_and_all_records_then_retries(self):
        before = self.snapshot()
        original = registry.record
        def broken(*args, **kwargs):
            original(*args, **kwargs)
            self.assertEqual(Review.objects.count(), 1)
            self.assertEqual(DeliveryCurrent.objects.get().revision, 3)
            raise DomainError('storage_unavailable', 'Retry later.', status=503)
        with patch.object(registry, 'record', broken):
            response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.snapshot(), before)
        first = self.post()
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(self.post().json(), first.json())
        self.assertEqual(Review.objects.count(), 1)
        for model in (AuditEvent, Outbox, IdempotencyResult):
            self.assertEqual(model.objects.filter(action_id='delivery.review').count(), 1)
        self.assertEqual(self.post(dict(self.body, decision=dict(outcome='request_changes', reason='Changed'))).status_code, 409)

    def test_explicit_optional_defaults_do_not_silently_change_idempotency_payload(self):
        url = f'/api/v1/issues/{self.issue["id"]}/deliveries'
        body = dict(workspace_id=self.workspace.pk, requirements_revision=1, summary='Omitted fields')
        response = self.post(body, url, key='omitted')
        self.assertEqual(response.status_code, 200, response.content)
        before = self.snapshot()
        for field, value in (('limitations', ''), ('artifact_ids', []), ('evidence', []), ('source_refs', [])):
            self.assertEqual(self.post(dict(body, **{field: value}), url, key='omitted').status_code, 409)
        self.assertEqual(self.snapshot(), before)
