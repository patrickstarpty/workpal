from django.test import TestCase

class LeaseHTTPTests(TestCase):
    def test_route(self):
        self.assertEqual(self.client.post('/api/runtime/v1/claim').status_code, 401)

    def test_storage_busy_mapping_is_retryable_and_redacted(self):
        from unittest.mock import patch
        from workpal.contracts import DomainError
        from workpal.execution import runtime_http
        payload = dict(version=1, capabilities=dict(provider_key='copilot_cli', version=1,
                       installed=True, authenticated=True, execution_ready=True))
        with patch.object(runtime_http.leases, 'claim', side_effect=DomainError(
                'storage_busy', 'private-storage-marker', status=503)):
            response = self.client.post('/api/runtime/v1/claim', payload,
                content_type='application/json', HTTP_AUTHORIZATION='Bearer wp_runtime_'+'a'*64)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'storage_busy')
        self.assertNotIn(b'private-storage-marker', response.content)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
