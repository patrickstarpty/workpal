import importlib.util
import json
import pathlib
import tempfile
import unittest

CHECKER = pathlib.Path(__file__).parents[1] / 'tools/check_contracts.py'

class ContractInventoryTests(unittest.TestCase):
    def check(self, routes, calls, complete=False):
        self.assertTrue(CHECKER.exists(), 'contract checker implementation missing')
        spec = importlib.util.spec_from_file_location('check_contracts', CHECKER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            r, c = pathlib.Path(directory)/'routes.json', pathlib.Path(directory)/'calls.json'
            r.write_text(json.dumps(routes)); c.write_text(json.dumps(calls))
            return module.check_contracts(r, c, require_complete=complete)

    def test_unmapped_frontend_call_fails(self):
        self.assertTrue(any('unmapped' in e for e in self.check([], [{'id':'call'}])))

    def test_duplicate_method_path_fails(self):
        route = {'method':'GET', 'path':'/api/test'}
        self.assertTrue(any('duplicate' in e for e in self.check([route, route], [])))

    def test_incomplete_route_fails_release_gate(self):
        self.assertTrue(any('pending' in e for e in self.check([{'method':'GET','path':'/api/test','status':'pending'}], [], True)))

    def test_mutation_requires_event_disposition(self):
        self.assertTrue(any('event' in e for e in self.check([{'method':'POST','path':'/api/test'}], [])))

    def test_empty_inventory_fails(self):
        self.assertTrue(self.check([], []))

    def test_malformed_documents_fail_closed(self):
        self.assertTrue(self.check({'routes': 'wrong'}, {'calls': 12}))

    def test_non_http_producer_requires_event(self):
        errors = self.check({'routes': [], 'producers': [{'id': 'job', 'kind': 'scheduled'}]}, [])
        self.assertTrue(any('event' in e for e in errors))

    def test_fake_source_rejected(self):
        errors = self.check([{'method': 'GET', 'path': '/api/test', 'sources': ['invented evidence']}], [])
        self.assertTrue(any('reference' in e for e in errors))

class HardeningTests(ContractInventoryTests):
    ref = 'server/tests/test_contract_inventory.py:1::test_empty_inventory_fails'
    def record(self):
        return dict(method='GET', path='/ok', origin='go', sources=[self.ref], auth={'required':False}, scope={'kind':'process'}, fixtures={'request':{'body':None},'success':{'status':200,'body':{}},'errors':[{'status':400,'body':{'error':'bad'}}]}, dependencies={'tables':[]}, batch='one', status='implemented', tests=[self.ref])
    def complete(self,r):
        return self.check({'routes':[r],'producers':[],'producer_coverage':{'complete':True,'sources':[self.ref],'reason':'Bounded scope has no jobs'}},{'coverage':{'complete':True},'calls':[{'route':{'method':'GET','path':'/ok'},'sources':[self.ref]}]},True)
    def test_legitimate_complete(self):
        self.assertEqual([],self.complete(self.record()))
    def test_invalid_types(self):
        for m,p in [([], '/ok'),('GET',{}),('get','/ok'),('GET','oops')]:
            r=self.record();r.update(method=m,path=p);self.assertTrue(self.complete(r))
    def test_fake_test(self):
        r=self.record();r['tests']=[self.ref.replace('test_empty_inventory_fails','test_fake_name')];self.assertTrue(self.complete(r))
    def test_placeholder_fixture(self):
        r=self.record();r['fixtures']={'source_handler':'dump'};self.assertTrue(self.complete(r))
    def test_false_exemption(self):
        r=self.record();r.update(status='unsupported',decision='skip');self.assertTrue(self.complete(r))
    def test_missing_producer_declaration(self):
        self.assertTrue(self.check([self.record()],[{'route':{'method':'GET','path':'/ok'}}],True))

class ReadEventTests(HardeningTests):
    def test_explicit_required_read_events_have_mutation_validation(self):
        for method in ('GET', 'HEAD', 'OPTIONS'):
            for strict in (False, True):
                with self.subTest(method=method, strict=strict):
                    r = self.record()
                    r.update(method=method, event={'disposition': 'required', 'reason': 'Refresh commits an event', 'sources': [self.ref]})
                    errors = self.check([r], [], strict)
                    for field in ('producer', 'type', 'payload', 'scope', 'transaction', 'consumer'):
                        self.assertIn(f'{method} /ok: missing event {field}', errors)
                    for field in ('producer', 'transaction', 'consumer'):
                        self.assertIn(f'{method} /ok {field}: missing evidence references', errors)
                    if strict:
                        for field in ('commit_test', 'rollback_test', 'recovery_test'):
                            self.assertIn(f'{method} /ok: missing event {field}', errors)

    def test_read_event_invalid_declarations_fail_closed(self):
        for method in ('GET', 'HEAD', 'OPTIONS', 'POST'):
            for event in (None, [], 'required', {}, {'disposition': []}, {'disposition': 'unknown'}):
                with self.subTest(method=method, event=event):
                    r = self.record()
                    r.update(method=method, event=event)
                    self.assertTrue(any(f'{method} /ok:' in e and 'event' in e for e in self.check([r], [])))

    def test_complete_read_event_requires_real_test_references(self):
        r = self.record()
        r['event'] = dict(disposition='required', reason='Refresh commits an event', sources=[self.ref],
                          producer='refresh', type='pull_request:updated', payload={'id': 'id'}, scope='issue',
                          transaction='after commit', consumer='frontend', producer_sources=[self.ref],
                          transaction_sources=[self.ref], consumer_sources=[self.ref],
                          commit_test=self.ref, rollback_test=self.ref, recovery_test=self.ref)
        self.assertEqual([], self.complete(r))
        for field in ('commit_test', 'rollback_test', 'recovery_test'):
            bad = dict(r, event=dict(r['event'], **{field: 'server/tools/check_contracts.py:1'}))
            self.assertTrue(any(f'/ok {field}: reference must name a test function' in e for e in self.complete(bad)))

if __name__ == '__main__':
    unittest.main()
