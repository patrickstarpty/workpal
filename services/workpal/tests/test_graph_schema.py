from django.test import SimpleTestCase
from workpal.actions.schemas import check_schema, validate


class GraphLiteralSchemaTests(SimpleTestCase):
    def test_empty_schema_accepts_finite_json_literals(self):
        check_schema({})
        for value in (None, True, 1, 1.5, 'text', [], {}, {'a': [None, {'b': 2}]}):
            with self.subTest(value=value):
                validate(value, {})

    def test_empty_schema_rejects_non_json_literals(self):
        for value in (float('nan'), float('inf'), -float('inf'), '\ud800', {1: 'x'}, (1,), set(), object()):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises((ValueError, TypeError)):
                    validate(value, {})

    def test_objects_remain_closed(self):
        with self.assertRaises(ValueError):
            check_schema({'type': 'object', 'additionalProperties': True})
        schema = {'type': 'object', 'properties': {'value': {}},
                  'required': ['value'], 'additionalProperties': False}
        check_schema(schema)
        validate({'value': {'nested': [1, None]}}, schema)
        with self.assertRaises(ValueError):
            validate({'value': 1, 'extra': 2}, schema)

    def test_nullable_scalar_union_is_preserved(self):
        for kind, value in (('string', 'x'), ('integer', 1), ('number', 1.5), ('boolean', True)):
            schema = {'type': [kind, 'null']}
            check_schema(schema)
            validate(None, schema)
            validate(value, schema)
