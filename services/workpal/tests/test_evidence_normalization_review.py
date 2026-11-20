import json

from django.test import SimpleTestCase

from workpal.contracts import DomainError
from workpal.investigation.normalization import normalize_upload


class NormalizationReviewTests(SimpleTestCase):
    def policy(self):
        return dict(version=1, allow_text=False, allow_fields=['message'], redact_literals=[])

    def test_discarded_values_must_still_be_finite_unicode(self):
        values = ('1e999', '"\\ud800"', '[{"nested":-1e999}]', '{"nested":["\\udfff"]}')
        for value in values:
            with self.subTest(value=value):
                raw = ('{"message":"ok","ignored":' + value + '}').encode()
                with self.assertRaises(DomainError) as caught:
                    normalize_upload(raw, format='jsonl', policy=self.policy())
                self.assertEqual((caught.exception.code, caught.exception.status), ('invalid_upload', 400))
                self.assertIsNone(caught.exception.__cause__)
                self.assertTrue(caught.exception.__suppress_context__)

    def test_discarded_nested_json_is_allowed_and_dropped(self):
        raw = json.dumps({'message': 'ok', 'ignored': {'nested': [None, True, 1, 1.5, '中']}}).encode()
        result = normalize_upload(raw, format='jsonl', policy=self.policy())
        self.assertEqual(result['content'], '{"message":"ok"}')
        self.assertEqual(result['omitted_fields'], 1)

    def test_policy_exact_maximum_sizes_are_accepted(self):
        fields = [('field_' + str(i)).ljust(128, 'x') for i in range(100)]
        literals = [('secret_' + str(i)).ljust(256, 'y') for i in range(100)]
        policy = dict(version=1, allow_text=False, allow_fields=fields, redact_literals=literals)
        raw = json.dumps({fields[0]: literals[0]}).encode()
        result = normalize_upload(raw, format='jsonl', policy=policy)
        self.assertEqual(json.loads(result['content']), {fields[0]: '[REDACTED]'})
        self.assertEqual(result['redaction_count'], 1)
