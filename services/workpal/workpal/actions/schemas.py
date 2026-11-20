import json
from django import forms
from workpal.contracts import DomainError

def finite_json(value):
    if value is None or type(value) in (bool,int): return
    if type(value) is str:
        value.encode('utf-8')
        return
    if type(value) is float:
        json.dumps(value,allow_nan=False); return
    if type(value) is list:
        for item in value: finite_json(item)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for key, item in value.items():
            finite_json(key)
            finite_json(item)
        return
    raise ValueError('Only finite JSON values are supported')

def check_schema(s):
    if type(s) is dict and not s:
        return
    if isinstance(s, dict) and isinstance(s.get('type'), list):
        kinds = s['type']
        if (len(kinds) != 2 or any(type(kind) is not str for kind in kinds)
                or kinds.count('null') != 1):
            raise ValueError('Unsupported nullable schema')
        base = next(kind for kind in kinds if kind != 'null')
        if base not in ('string', 'integer', 'number', 'boolean'):
            raise ValueError('Unsupported nullable type')
        check_schema(dict(s, type=base))
        return
    if not isinstance(s,dict) or s.get('type') not in ('object','array','string','integer','boolean','number','null'):
        raise ValueError('Unsupported schema')
    if set(s)-{'type','properties','required','additionalProperties','items','enum','minimum','maximum','maxLength','minLength','minItems','maxItems'}:
        raise ValueError('Unsupported schema keyword')
    for key in ('minItems', 'maxItems'):
        if key in s and (s['type'] != 'array' or type(s[key]) is not int or s[key] < 0):
            raise ValueError('Invalid array bound')
    if 'minItems' in s and 'maxItems' in s and s['minItems'] > s['maxItems']:
        raise ValueError('Invalid array bounds')
    if s['type']=='object':
        if s.get('additionalProperties') is not False: raise ValueError('Objects must be closed')
        for v in s.get('properties',{}).values(): check_schema(v)
        if not set(s.get('required',[])) <= set(s.get('properties',{})): raise ValueError('Unknown required field')
    if s['type']=='array': check_schema(s['items'])
    finite_json(s)

def validate(value,s):
    finite_json(value)
    if type(s) is dict and not s:
        return
    if isinstance(s['type'], list):
        check_schema(s)
        if value is None:
            if 'enum' in s and None not in s['enum']:
                raise ValueError('Invalid choice')
            return
        return validate(value, dict(s, type=next(kind for kind in s['type'] if kind != 'null')))
    types={'object':dict,'array':list,'string':str,'integer':int,'boolean':bool,'number':(int,float),'null':type(None)}
    expected=types[s['type']]
    if (type(value) not in expected if isinstance(expected,tuple) else type(value) is not expected): raise ValueError('Invalid JSON type')
    if 'enum' in s and value not in s['enum']: raise ValueError('Invalid choice')
    for key,invalid in (('minItems',lambda x:len(value)<x),('maxItems',lambda x:len(value)>x),('minimum',lambda x:value<x),('maximum',lambda x:value>x),('maxLength',lambda x:len(value)>x),('minLength',lambda x:len(value)<x)):
        if key in s and invalid(s[key]): raise ValueError('Value outside bounds')
    if s['type']=='object':
        props=s.get('properties',{})
        if set(value)-set(props) or set(s.get('required',[]))-set(value): raise ValueError('Invalid fields')
        for k,v in value.items(): validate(v,props[k])
    if s['type']=='array':
        for v in value: validate(v,s['items'])

class StructuredField(forms.Field):
    def __init__(self, *, schema, **kwargs):
        check_schema(schema)
        self.schema = schema
        super().__init__(**kwargs)
    def clean(self, value):
        if value is None and not self.required: return None
        try: validate(value, self.schema)
        except (ValueError, TypeError): raise forms.ValidationError('Invalid structured value.')
        self.run_validators(value)
        return value

def form_schema(cls):
    props={}; required=[]
    for name,f in cls.base_fields.items():
        mapping={forms.CharField:'string',forms.IntegerField:'integer',forms.BooleanField:'boolean',forms.ChoiceField:'string'}
        if type(f) is StructuredField:
            props[name]=f.schema
            if f.required: required.append(name)
            continue
        if type(f) not in mapping: raise ValueError('Unsupported form field')
        s={'type':mapping[type(f)]}
        if type(f) is forms.ChoiceField:
            if any(type(k) is not str for k,v in f.choices): raise ValueError('Choices must be strings')
            s['enum']=[k for k,v in f.choices]
        for attr,key in [('min_value','minimum'),('max_value','maximum'),('max_length','maxLength'),('min_length','minLength')]:
            v=getattr(f,attr,None)
            if v is not None: s[key]=v
        props[name]=s
        if f.required: required.append(name)
    return {'type':'object','properties':props,'required':required,'additionalProperties':False}

def clean(cls,payload):
    try: validate(payload,form_schema(cls))
    except (ValueError,TypeError): raise DomainError('invalid_input','Invalid action fields.')
    form=cls(payload)
    if not form.is_valid(): raise DomainError('invalid_input','Invalid action fields.')
    return form.cleaned_data
