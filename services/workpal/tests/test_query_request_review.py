import dataclasses
import hashlib
import json
import unittest

from workpal.contracts import DomainError
from workpal.investigation.query_requests import normalize_query_request as norm, parse_query_request as parse


class QueryRequestReviewTests(unittest.TestCase):
    def base(self, **changes):
        return dict(source_id=1, service=2, capability='search_logs', key='private-key', **changes)

    def rejected(self, function, value):
        with self.assertRaises(DomainError) as caught:
            function(value)
        error = caught.exception
        self.assertEqual((error.code, error.status, error.message, error.details),
                         ('invalid_input', 400, 'Invalid query request.', {}))
        self.assertNotIn('private-key', str(error))

    def test_duplicate_known_fields_and_strict_direct_types(self):
        valid = b'{"source_id":1,"service":2,"capability":"search_logs","key":"private-key"}'
        self.assertEqual(parse(valid), norm(self.base()))
        # Both duplicate variants would otherwise normalize to a legal request.
        for suffix in (b',"source_id":1}', b',"filters":{"text":"ok","text":"ok"}}'):
            with self.subTest(suffix=suffix):
                self.rejected(parse, valid[:-1] + suffix)
        for name, base_type, value in [('id', int, 1), ('text', str, 'ok'), ('mapping', dict, self.base())]:
            subtype = type('Subtype', (base_type,), {})
            wrapped = subtype(value)
            case = self.base()
            if name == 'id': case['service'] = wrapped
            elif name == 'text': case['filters'] = {'text': wrapped}
            else: case = wrapped
            self.rejected(norm, case)
        for changes in ({'service': False}, {'service': 2**63}, {'capability': ['search_logs']},
                        {'filters': {'unexpected': 'private-key'}}, {'time_window': {}},
                        {'filters': {'text': float('inf')}}, {'cursor': b'cursor'}):
            case = self.base(); case.update(changes)
            with self.subTest(changes=changes): self.rejected(norm, case)
        self.rejected(norm, {**self.base(), 1: 'private-key'})

    def test_window_markers_microseconds_and_explicit_hash(self):
        marker = norm(self.base())
        nulls = norm(self.base(time_window=None, timezone=None, cursor=None, filters={}))
        self.assertEqual(marker, nulls)
        request = self.base(time_window={'start':'0001-01-01T00:00:00.000001Z',
                                        'end':'0001-01-01T01:00:00.000002Z'}, timezone='GMT')
        result = norm(request)
        canonical = b'{"capability":"search_logs","cursor":null,"filters":{},"service":2,"source_id":1,"time_window":{"end":"0001-01-01T01:00:00.000002Z","start":"0001-01-01T00:00:00.000001Z"},"timezone":"GMT"}'
        self.assertEqual(result.input_hash, hashlib.sha256(b'query-v1\0' + canonical).hexdigest())
        self.assertNotEqual(result.input_hash, marker.input_hash)
        for field in ('start', 'end'):
            with self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(result.time_window, field, result.time_window.start)
        request['time_window']['start'] = '2020-01-01T00:00:00Z'
        self.assertEqual(result.time_window.start.year, 1)
        for start, end in [('2020-01-02T00:00:00Z','2020-01-01T00:00:00Z'),
                           ('2020-01-01T00:00:00+00:60','2020-01-02T00:00:00Z'),
                           ('2020-01-01T00:00:60Z','2020-01-02T00:00:00Z'),
                           ('2020-01-01T00:00:00.1234567Z','2020-01-02T00:00:00Z'),
                           ('9999-12-31T22:00:00Z','9999-12-31T23:59:59-01:00')]:
            with self.subTest(start=start, end=end):
                self.rejected(norm, self.base(time_window=dict(start=start, end=end)))

    def test_text_preservation_and_bad_encodings_have_fixed_errors(self):
        request = self.base(filters={'level':'warn','text':'  e\u0301😀  '}, cursor='  cursor  ')
        result = norm(request)
        self.assertEqual(result, parse(json.dumps(request, ensure_ascii=True).encode()))
        self.assertEqual(result.filters.text, request['filters']['text'])
        self.assertEqual(result.cursor, '  cursor  ')
        composed = dict(request, filters={'level':'warn', 'text':'  é😀  '})
        self.assertNotEqual(result.input_hash, norm(composed).input_hash)
        with self.assertRaises(dataclasses.FrozenInstanceError): result.filters.text = 'new'
        for zone in ('Not/A_Real_Zone', '+08:00', '/UTC', 'UTC/', 'A//B', 'A/../UTC', 'A\\B', 'x'*101):
            with self.subTest(zone=zone): self.rejected(norm, self.base(timezone=zone))
        raw = json.dumps(self.base()).encode()
        for data in (raw[:-1]+b',"filters":{"text":NaN}}',
                     raw[:-1]+b',"filters":{"text":1e999}}',
                     raw[:-1]+b',"filters":{"text":"\\ud800"}}',
                     b'\xffprivate-key', bytearray(raw), raw.decode()):
            with self.subTest(data=data): self.rejected(parse, data)
