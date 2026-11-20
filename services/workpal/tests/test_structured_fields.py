from django import forms
from django.test import SimpleTestCase
from workpal.actions import schemas

class StructuredFields(SimpleTestCase):
    def test_array_bounds(self):
        schema={'type':'array','items':{'type':'string'},'minItems':1,'maxItems':2}
        with self.assertRaises(ValueError): schemas.validate([],schema)
        with self.assertRaises(ValueError): schemas.validate(['a','b','c'],schema)

    def test_closed_nested_schema_roundtrip(self):
        from workpal.contracts import DomainError
        schema={'type':'array','maxItems':2,'items':{'type':'object','properties':{'id':{'type':'string'}},'required':['id'],'additionalProperties':False}}
        class Form(forms.Form):
            refs=schemas.StructuredField(schema=schema,required=False)
        self.assertEqual(schemas.form_schema(Form)['properties']['refs'],schema)
        for value in ([],[{'id':'a'}]):
            self.assertEqual(schemas.clean(Form,{'refs':value})['refs'],value)
        for value in ('[]',None,[{'id':'a','extra':1}],[{'id':True}],[{}, {}, {}]):
            with self.assertRaises(DomainError): schemas.clean(Form,{'refs':value})
        with self.assertRaises(ValueError): schemas.StructuredField(schema={**schema,'unknown':True})
