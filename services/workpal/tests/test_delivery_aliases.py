from django.test import Client
from tests.support import WorkpalCase
from tests.test_review_validation import ReviewFixtures


class DeliveryAliases(ReviewFixtures, WorkpalCase):
    def test_submit_route(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        token = client.get('/api/v1/auth/csrf').json()['csrf_token']
        response = client.post(f'/api/v1/issues/{self.issue["id"]}/deliveries',
            dict(workspace_id=self.workspace.pk, requirements_revision=1, summary='HTTP delivery'),
            content_type='application/json', HTTP_X_CSRFTOKEN=token, HTTP_IDEMPOTENCY_KEY='http')
        self.assertEqual(response.status_code, 200)

    def http(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.token = client.get('/api/v1/auth/csrf').json()['csrf_token']
        return client

    def post(self, client, body=None, key='alias', path=None, **headers):
        return client.post(path or f'/api/v1/issues/{self.issue["id"]}/deliveries',
            body if body is not None else self.body(), content_type='application/json',
            HTTP_X_CSRFTOKEN=self.token, HTTP_IDEMPOTENCY_KEY=key, **headers)

    def body(self):
        return dict(workspace_id=self.workspace.pk, requirements_revision=1, summary='HTTP delivery')

    def review_body(self, target):
        return dict(workspace_id=self.workspace.pk, revision=2, version=target['number'],
                    decision=dict(outcome='approve', reason='Human review.'))

    def test_review_route(self):
        target = self.ready()
        response = self.post(self.http(), self.review_body(target), path=f'/api/v1/deliveries/{target["id"]}/reviews')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['decision']['outcome'], 'approve')

    def test_submit_bidirectional_replay(self):
        client = self.http()
        body = self.body()
        payload = dict(subject=self.subject, requirements_revision=1, summary=body['summary'])
        for first in ('generic', 'alias'):
            key = first
            generic = lambda: self.post(client, dict(workspace_id=self.workspace.pk, payload=payload,
                idempotency_key=key), path='/api/v1/actions/delivery.submit', key=key)
            alias = lambda: self.post(client, body, key=key)
            a = generic() if first == 'generic' else alias()
            self.assertEqual(a.status_code, 200)
            before = self.snapshot()
            b = alias() if first == 'generic' else generic()
            self.assertEqual(b.status_code, 200)
            self.assertEqual(a.json()['data'] if first == 'generic' else a.json(), b.json() if first == 'generic' else b.json()['data'])
            self.assertEqual(self.snapshot(), before)

    def test_review_bidirectional_replay(self):
        client = self.http()
        target = self.ready()
        for first in ('generic', 'alias'):
            body = self.review_body(target)
            body['revision'] = self.current().data['revision']
            key = 'review-' + first
            generic_body = dict(workspace_id=self.workspace.pk, expected_revision=body['revision'],
                idempotency_key=key, payload=dict(delivery_id=target['id'], version=target['number'], decision=body['decision']))
            path = f'/api/v1/deliveries/{target["id"]}/reviews'
            generic = lambda: self.post(client, generic_body, key, '/api/v1/actions/delivery.review')
            alias = lambda: self.post(client, body, key, path)
            a = generic() if first == 'generic' else alias()
            self.assertEqual(a.status_code, 200)
            before = self.snapshot()
            b = alias() if first == 'generic' else generic()
            self.assertEqual(b.status_code, 200)
            self.assertEqual(a.json()['data'] if first == 'generic' else a.json(), b.json() if first == 'generic' else b.json()['data'])
            self.assertEqual(self.snapshot(), before)

    def test_changed_payload_conflict(self):
        client = self.http()
        self.assertEqual(self.post(client).status_code, 200)
        self.assertEqual(self.post(client, dict(self.body(), summary='changed')).status_code, 409)

    def test_stale_review(self):
        target = self.ready()
        body = dict(self.review_body(target), revision=1)
        self.assertEqual(self.post(self.http(), body, path=f'/api/v1/deliveries/{target["id"]}/reviews').status_code, 409)

    def test_closed_fields(self):
        client = self.http()
        for field in ('subject', 'issue_id', 'revision', 'user_id', 'executor_id', 'approved', 'unknown'):
            with self.subTest(field=field):
                self.assertEqual(self.post(client, dict(self.body(), **{field: 1})).status_code, 400)

    def test_integer_matrix(self):
        client = self.http()
        for value in (True, False, 0, -1, '1', None, 9223372036854775808):
            self.assertEqual(self.post(client, dict(self.body(), workspace_id=value)).status_code, 400)
        for value in ('0', '9223372036854775807', '9223372036854775808'):
            self.assertEqual(self.post(client, path=f'/api/v1/issues/{value}/deliveries').status_code, 400)

    def test_json_query_and_size(self):
        client = self.http()
        for body in ('{', '{"workspace_id":1,"workspace_id":1}', '{"x":NaN}', '{"x":"\\ud800"}'):
            self.assertEqual(self.post(client, body).status_code, 400)
        self.assertEqual(self.post(client, ' ' * (1024 * 1024 + 1)).status_code, 413)
        self.assertEqual(self.post(client, path=f'/api/v1/issues/{self.issue["id"]}/deliveries?x=1').status_code, 400)

    def test_security_controls(self):
        client = self.http()
        path = f'/api/v1/issues/{self.issue["id"]}/deliveries'
        self.assertEqual(client.get(path).status_code, 405)
        self.assertEqual(client.post(path, self.body(), content_type='application/json').status_code, 403)
        self.assertEqual(self.post(client, HTTP_HOST='evil.invalid').status_code, 400)
        client.logout()
        self.assertEqual(self.post(client).status_code, 403)
        client.force_login(self.user)
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.post(client).status_code, 403)

    def test_headers(self):
        client = self.http()
        for key in ('', ' '):
            response = self.post(client, key=key)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(self.post(client, HTTP_X_CONFIRMATION_ID=' ').status_code, 400)

    def test_rollback_after_audit_and_retry(self):
        from unittest.mock import patch
        from workpal.actions import registry
        client = self.http()
        before = self.snapshot()
        original = registry.record
        def broken(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('private failure detail')
        with patch.object(registry, 'record', broken):
            response = self.post(client)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('private failure detail', response.content.decode())
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.post(client).status_code, 200)

    def test_current_source_revocation_blocks_both_aliases_and_replay(self):
        from workpal.access.models import SourceGrant
        client = self.http()
        target = self.ready()
        review_body = self.review_body(target)
        path = f'/api/v1/deliveries/{target["id"]}/reviews'
        self.assertEqual(self.post(client).status_code, 200)
        self.assertEqual(self.post(client, review_body, 'review-http', path).status_code, 200)
        SourceGrant.objects.filter(user=self.user).update(read=False, write=False)
        for key in ('alias', 'new'):
            self.assertEqual(self.post(client, key=key).status_code, 403)
        for key in ('review-http', 'new-review'):
            self.assertEqual(self.post(client, review_body, key, path).status_code, 403)

    def test_shared_user_cannot_cross_workspace(self):
        from workpal.identity.models import Membership
        Membership.objects.create(user=self.user, workspace=self.other, role='owner')
        client = self.http()
        self.assertEqual(self.post(client, dict(self.body(), workspace_id=self.other.pk)).status_code, 404)
        target = self.ready()
        body = dict(self.review_body(target), workspace_id=self.other.pk)
        self.assertEqual(self.post(client, body, path=f'/api/v1/deliveries/{target["id"]}/reviews').status_code, 404)
