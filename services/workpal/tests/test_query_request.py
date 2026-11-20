import dataclasses
import json
import os
import subprocess
import sys
import unittest
from workpal.contracts import DomainError
from workpal.investigation.query_requests import normalize_query_request as norm, parse_query_request as parse

class QueryRequestTests(unittest.TestCase):
    def base(self, **kw):
        return dict(source_id=1, service=1, capability='search_logs', key='k', **kw)

    def bad(self, value):
        with self.assertRaises(DomainError) as cm:
            norm(value)
        self.assertEqual((cm.exception.code, cm.exception.status, cm.exception.message), ('invalid_input',400,'Invalid query request.'))

    def test_equivalence_and_hash(self):
        v = self.base()
        self.assertEqual(norm(v), parse(json.dumps(v).encode()))
        import hashlib
        literal = b'{"capability":"search_logs","cursor":null,"filters":{},"service":1,"source_id":1,"time_window":null,"timezone":null}'
        self.assertEqual(norm(v).input_hash, hashlib.sha256(b'query-v1\0'+literal).hexdigest())
        v['key']='different'
        self.assertEqual(norm(v).input_hash,norm(self.base()).input_hash)

    def test_shape_ids_types(self):
        for field in ('source_id','service','capability','key'):
            v=self.base(); del v[field]; self.bad(v)
            v=self.base(); v[field]=None; self.bad(v)
        for x in (True,0,-1,2**63,1.0,'1'):
            v=self.base(); v['source_id']=x; self.bad(v)
        norm(dict(self.base(),source_id=2**63-1))
        for extra in ({'extra':1},{'filters':None},{'filters':{'level':None}},{'filters':{'text':None}},{'cursor':()},{'timezone':'../UTC'}):
            self.bad(dict(self.base(),**extra))
        v=self.base(); v['filters']=v; self.bad(v)

    def test_raw_json(self):
        raw=json.dumps(self.base()).encode()
        self.assertEqual(parse(raw+b' '*(16384-len(raw))),norm(self.base()))
        for b in (raw+b' '*(16385-len(raw)), b'\xef\xbb\xbf'+raw,b'\xff',b'{"a":1,"a":2}', b'NaN',raw+b'{}',b'[]'):
            with self.assertRaises(DomainError): parse(b)

    def test_strings(self):
        for field,limit in (('key',200),('cursor',2048)):
            norm(dict(self.base(),**{field:'x'*limit}))
            for x in ('','x'*(limit+1),'a\x00','\ud800','\x7f'):
                self.bad(dict(self.base(),**{field:x}))
        norm(self.base(filters={'text':' '*1024},cursor=' '))
        for x in ('','x'*1025): self.bad(self.base(filters={'text':x}))
        self.bad(dict(self.base(),key=' '))

    def test_windows_timezone(self):
        a=self.base(time_window={'start':'0001-01-01T00:00:00Z','end':'0001-01-02T00:00:00Z'})
        norm(a)
        for tz in ('UTC','GMT','CET','Asia/Shanghai'): norm(self.base(timezone=tz))
        for start,end in (('2020-01-01','2020-01-02'),('2020-01-01T00:00:00-00:00','2020-01-02T00:00:00Z'),('2020-01-01T00:00:00+24:00','2020-01-02T00:00:00Z'),('0001-01-01T00:00:00+01:00','0001-01-02T00:00:00Z')):
            self.bad(self.base(time_window=dict(start=start,end=end)))
        x=self.base(time_window=dict(start='2020-01-01T00:00:00Z',end='2020-01-02T00:00:00Z'))
        y=self.base(time_window=dict(start='2020-01-01T01:00:00+01:00',end='2020-01-02T01:00:00+01:00'))
        self.assertEqual(norm(x),norm(y))
        x['time_window']['end']=x['time_window']['start']; self.bad(x)

    def test_frozen_defaults_isolation(self):
        v=self.base(filters={'text':'original'}); r=norm(v); v['filters']['text']='changed'
        self.assertEqual(r.filters.text,'original')
        with self.assertRaises(dataclasses.FrozenInstanceError): r.key='x'
        self.assertEqual(norm(self.base()),norm(self.base(time_window=None,timezone=None,cursor=None)))
        env=dict(os.environ); env.pop('DJANGO_SETTINGS_MODULE',None); env['PYTHONPATH']=os.path.dirname(os.path.dirname(__file__))
        code="""from workpal.investigation.query_requests import normalize_query_request as n
from workpal.contracts import DomainError
v=dict(source_id=1,service=1,capability='search_logs',key='k')
if n(v) != n(v): raise RuntimeError('unstable request')
try: n(dict(v,source_id=True))
except DomainError as e:
    if (e.code,e.status) != ('invalid_input',400): raise RuntimeError('wrong rejection')
else: raise RuntimeError('invalid request accepted')
"""
        for flag in ([],['-O']):
            subprocess.run([sys.executable,*flag,'-c',code],env=env,check=True)
