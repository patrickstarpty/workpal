import hashlib
from django.test import SimpleTestCase
from workpal.investigation.normalization import normalize_upload

class NormalizationTests(SimpleTestCase):
    def policy(self, **changes):
        return dict(version=1, allow_text=True, allow_fields=['message'], redact_literals=['secret'], **changes)

    def test_text_excerpt_masks_and_hashes_real_bytes(self):
        raw = b'secret hello'
        result = normalize_upload(raw, format='text', policy=self.policy())
        self.assertEqual(result['content'], '[REDACTED] hello')
        self.assertEqual(result['raw_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(result['raw_sha256'], result['content_sha256'])
        self.assertEqual((result['origin'], result['coverage']), ('user_upload', 'uploaded_excerpt'))

    def run_upload(self, raw, fmt='text', policy=None):
        return normalize_upload(raw, format=fmt, policy=self.policy() if policy is None else policy)

    def rejected(self, raw, fmt='text', policy=None, code='invalid_upload', status=400):
        from workpal.contracts import DomainError
        import contextlib
        import io
        import traceback
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(DomainError) as caught:
                self.run_upload(raw, fmt, policy)
        error = caught.exception
        self.assertEqual((error.code, error.status), (code, status))
        self.assertNotIn('secret', str(error) + str(error.details))
        self.assertIsNone(error.__cause__)
        self.assertTrue(error.__suppress_context__)
        self.assertEqual(stdout.getvalue() + stderr.getvalue(), '')

    def test_json_scalars_canonical_and_omission(self):
        p = self.policy()
        p['allow_fields'] = ['z', 'a', 'b', 'n', 'message']
        r = self.run_upload(b'{"z":1,"a":null,"b":true,"n":1.5,"message":"secret","drop":{"x":2}}', 'jsonl', p)
        self.assertEqual(r['content'], '{"a":null,"b":true,"message":"[REDACTED]","n":1.5,"z":1}')
        self.assertEqual(r['omitted_fields'], 1)
        self.assertEqual(r['content_sha256'], hashlib.sha256(r['content'].encode()).hexdigest())
        self.assertEqual(self.run_upload(b'{"drop":1}', 'jsonl')['content'], '{}')

    def test_input_byte_limits_before_decoding(self):
        self.assertEqual(self.run_upload(b'x' * 2097152)['content_bytes'], 2097152)
        self.rejected(b'\xff' * 2097153, code='upload_too_large', status=413)

    def test_records_and_unparsed_truncated_tail(self):
        raw = b'\n' + b'{}\n' * 1000 + b'not JSON secret'
        r = self.run_upload(raw, 'jsonl')
        self.assertEqual((r['total_records'], r['included_records'], r['status'], r['truncated']), (1001, 1000, 'truncated', True))
        self.assertEqual(r['included_line_numbers'], list(range(2, 1002)))
        self.assertFalse(self.run_upload(b'x\n' * 1000)['truncated'])
        self.assertEqual(r['raw_sha256'], hashlib.sha256(raw).hexdigest())

    def test_blank_bom_crlf_unicode_and_line_numbers(self):
        for raw in (b'', b' \r\n\t\n', b'\xef\xbb\xbf'):
            r = self.run_upload(raw)
            self.assertEqual((r['content'], r['status'], r['included_records']), ('', 'no_data', 0))
        r = self.run_upload('\ufeff\n  中  \r\n\nend\r\n'.encode())
        self.assertEqual(r['content'], '  中  \nend')
        self.assertEqual(r['included_line_numbers'], [2, 4])

    def test_invalid_uploads_are_private(self):
        for raw, fmt in [(bytearray(b'x'), 'text'), ('secret', 'text'), (b'\xffsecret', 'text'), (b'x', 'bad'), (b'{secret', 'jsonl'), (b'{"message":1,"message":2}', 'jsonl'), (b'{"x":NaN}', 'jsonl'), (b'{"x":Infinity}', 'jsonl'), (b'[]', 'jsonl'), (b'{"message":[]}', 'jsonl'), (b'{"message":{}}', 'jsonl'), (b'{"message":1e999}', 'jsonl'), (b'{"message":"\\ud800"}', 'jsonl')]:
            with self.subTest(raw=repr(raw), fmt=fmt):
                self.rejected(raw, fmt)

    def test_closed_policy_validation(self):
        policies = [{}, dict(self.policy(), extra=1), dict(self.policy(), version=True), dict(self.policy(), version=2), dict(self.policy(), allow_text=1)]
        for key in ('allow_fields', 'redact_literals'):
            for value in ('x', ['x', 'x'], [''], ['x'] * 101, [1], ['\ud800'], ['x' * (129 if key == 'allow_fields' else 257)]):
                policies.append(dict(self.policy(), **{key: value}))
        policies.append(dict(self.policy(), allow_fields=['secret_field']))
        for p in policies:
            with self.subTest(policy=repr(p)):
                self.rejected(b'secret', policy=p, code='invalid_redaction_policy')
        self.rejected(b'secret', policy=dict(self.policy(), allow_text=False), code='text_upload_not_allowed', status=403)

    def test_literals_longest_once_and_inert(self):
        p = dict(self.policy(), redact_literals=['ab', 'abc', '[REDACTED]', '.*', '$(exit)', '中'])
        r = self.run_upload('abcab .* $(exit) 中'.encode(), policy=p)
        self.assertEqual(r['content'], '[REDACTED][REDACTED] [REDACTED] [REDACTED] [REDACTED]')
        self.assertEqual(r['redaction_count'], 5)

    def test_policy_hash_and_mutation_isolation(self):
        import json
        p = dict(self.policy(), allow_fields=['z', 'message'], redact_literals=['secret', 'private'])
        first = self.run_upload(b'secret', policy=p)
        p['allow_fields'].reverse()
        p['redact_literals'].reverse()
        second = self.run_upload(b'secret', policy=p)
        self.assertEqual(first, second)
        canonical = json.dumps(p, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        self.assertEqual(first['policy_sha256'], hashlib.sha256(canonical.encode()).hexdigest())
        first['included_line_numbers'].append(88)
        p['redact_literals'].clear()
        self.assertEqual(second['included_line_numbers'], [1])
        self.assertEqual(second['content'], '[REDACTED]')

    def test_output_expansion_and_quiet_success(self):
        import contextlib
        import io
        self.rejected(b'a' * 210000, policy=dict(self.policy(), allow_fields=[], redact_literals=['a']), code='normalized_upload_too_large', status=413)
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            self.run_upload(b'hello')
        self.assertEqual(stream.getvalue(), '')
