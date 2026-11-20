"""Independent checks through the query management Interface."""
from django.test import TestCase
from tests import test_query_configuration as fixtures
from workpal.investigation import query_config
from workpal.investigation.normalization import normalize_upload


class QueryPolicyHashReviewTests(TestCase):
    setUp = fixtures.QueryConfigurationTests.setUp

    def test_query_policy_hash_uses_existing_normalization_contract(self):
        policy = dict(version=1, allow_text=True,
                      allow_fields=['zeta', 'alpha'],
                      redact_literals=['secret-z', 'secret-a'])
        expected = normalize_upload(b'', format='jsonl', policy=policy)['policy_sha256']
        result = query_config.configure_policy(self.actor, self.source, policy, 1)
        self.assertEqual(result['policy_sha256'], expected)
        saved = query_config.read_policy(self.actor, self.source)
        self.assertEqual(saved['policy'], policy)
        self.assertEqual(saved['policy_sha256'], expected)

from copy import deepcopy
from workpal.contracts import ActionRequest, DomainError
from workpal.actions.registry import execute


class QueryConfigurationReviewTests(TestCase):
    setUp = fixtures.QueryConfigurationTests.setUp
    snapshot = fixtures.QueryConfigurationTests.snapshot
    confirmed = fixtures.QueryConfigurationTests.confirmed
    configure = fixtures.QueryConfigurationTests.configure

    def test_closed_config_direct_and_registry(self):
        query_config.configure_policy(self.actor, self.source, self.policy, 1)
        variants = [None, [], {}, dict(self.config, extra=1)]
        for field in self.config:
            value = deepcopy(self.config); del value[field]; variants.append(value)
        for field, values in {
            'version': [True, 0, 2, '1'],
            'method': ['POST', None, 1], 'network_zone': ['PUBLIC', None],
            'capabilities': [[], ['search_logs', 'search_logs'], 'search_logs'],
            'parameter_schema': [None, 'other'], 'response_mapping': [None, 'other'],
            'secret_ref': ['', 'a b', 'a\n', 'x'*201],
            'endpoint': ['http://logs.example.com/x', 'https://a@logs.example.com/x',
                         'https://logs.example.com:444/x', 'https://127.0.0.1/x',
                         'https://[::1]/x', 'https://logs.example.com/./x',
                         'https://logs.example.com/%41', 'https://logs.example.com/x?q=1',
                         'https://logs.example.com/x#f', 'https://é.example/x',
                         'https://-a.example/x', 'https://a..example/x',
                         'https://logs.example.com/\n', 'x'*2049],
        }.items():
            variants.extend(dict(self.config, **{field: value}) for value in values)
        for field, values in {'reference': ['', 'x'*1001, True],
                              'attestation': ['', 'x'*2001, None],
                              'sha256': ['a'*63, 'a'*65, 'A'*64, True]}.items():
            for value in values:
                config = deepcopy(self.config); config['readonly_proof'][field] = value
                variants.append(config)
        variants.extend(dict(self.config, readonly_proof=value) for value in (None, {}, dict(self.config['readonly_proof'], extra=1)))
        for index, config in enumerate(variants):
            for registry in (False, True):
                with self.subTest(index=index, registry=registry):
                    before = self.snapshot()
                    with self.assertRaises(DomainError) as caught:
                        if registry:
                            execute(self.actor, ActionRequest('query_config.configure', dict(source_id=self.source, config=config), 1, 'invalid-'+str(index)))
                        else:
                            query_config.configure(self.actor, self.source, config, 1)
                    self.assertEqual((caught.exception.code, caught.exception.status), ('invalid_input', 400))
                    self.assertEqual(before, self.snapshot())

    def test_confirmation_binding_expiry_and_replay(self):
        from workpal.actions.models import Confirmation
        from django.utils import timezone
        from datetime import timedelta
        for action, field, value in (('query_policy.configure', 'policy', self.policy),
                                     ('query_config.configure', 'config', self.config)):
            request = self.confirmed(action, {field: value}, field)
            for change in ('key', 'revision', 'payload', 'action'):
                altered = deepcopy(request)
                if change == 'key': altered.idempotency_key = 'changed'
                elif change == 'revision': altered.expected_revision = 2
                elif change == 'action': altered.action_id = 'query_config.configure' if field == 'policy' else 'query_policy.configure'
                elif field == 'policy':
                    altered.payload[field]['allow_text'] = not value['allow_text']
                else:
                    altered.payload[field]['readonly_proof']['attestation'] = 'Another valid attestation'
                before = self.snapshot()
                with self.assertRaises(DomainError) as caught: execute(self.actor, altered)
                if change != 'action':
                    self.assertEqual((caught.exception.code, caught.exception.status), ('confirmation_conflict', 409))
                self.assertEqual(before, self.snapshot())
            token = Confirmation.objects.get(pk=request.confirmation_id)
            original = token.expires_at
            token.expires_at = timezone.now()-timedelta(seconds=1); token.save()
            before = self.snapshot()
            with self.assertRaises(DomainError): execute(self.actor, request)
            self.assertEqual(before, self.snapshot())
            token.expires_at = original; token.save()
            execute(self.actor, request)
            before = self.snapshot(); execute(self.actor, request)
            self.assertEqual(before, self.snapshot())
