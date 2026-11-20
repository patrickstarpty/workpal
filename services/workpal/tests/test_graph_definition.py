from django.test import SimpleTestCase
from workpal.workflows.graph import compile_graph, evaluate_condition
from workpal.contracts import DomainError

def basic():
    return dict(nodes=[dict(id='start',type='start',config={}),dict(id='end',type='end',config={})],edges=[dict(**{'from':'start','to':'end'},on='always',required=True,max_traversals=0)],declared_fields=['x'])

class GraphDefinitionTests(SimpleTestCase):
    def test_normalization(self):
        d=basic(); result=compile_graph(d)
        self.assertEqual(result['schema_version'],1)
        d['nodes'].reverse()
        self.assertEqual(result,compile_graph(d))
        d['nodes'][0]['config']['bad']=1
        self.assertEqual(result['definition']['nodes'][0]['config'],{})
    def test_conditions(self):
        for op,value,expected in [('eq',2,True),('ne',3,True),('in',[2],True),('gt',1,True),('gte',2,True),('lt',3,True),('lte',2,True),('exists',True,True)]:
            self.assertEqual(evaluate_condition(dict(field='x',op=op,value=value),{'x':2},['x']),expected)
            self.assertFalse(evaluate_condition(dict(field='x',op=op,value=value),{},['x']))
    def test_invalid_graphs(self):
        for change in [lambda d:d.update(extra=1),lambda d:d['edges'][0].update(to='missing'),lambda d:d['edges'][0].update(required=1),lambda d:d['edges'][0].update(max_traversals=True),lambda d:d['nodes'][0].update(config={'bad':1})]:
            d=basic();change(d)
            with self.assertRaises(DomainError):compile_graph(d)
    def test_invalid_conditions(self):
        for c in [dict(field='x',op='eval',value='bad'),dict(field='x',op='in',value=2),dict(field='x',op='eq',value=float('nan'))]:
            with self.assertRaises(DomainError):evaluate_condition(c,{},['x'])
    def test_parallel_join_and_optional_edge(self):
        d=basic(); d['nodes'] += [dict(id='fork',type='parallel',config={}),dict(id='join',type='join',config={'mode':'all_required'})]
        def edge(a,b,required=True): return {'from':a,'to':b,'on':'always','required':required,'max_traversals':0}
        d['edges']=[edge('start','fork'),edge('fork','join'),edge('fork','end',False),edge('join','end')]
        s=compile_graph(d)
        self.assertTrue(any(not e['required'] for e in s['definition']['edges']))
        d['edges'].reverse(); self.assertEqual(s,compile_graph(d))
    def test_bounded_rework_and_overlapping_unbounded_cycle(self):
        d=basic();d['nodes'] += [dict(id='fork',type='parallel',config={}),dict(id='again',type='parallel',config={})]
        def edge(a,b,count=0):return {'from':a,'to':b,'on':'always','required':True,'max_traversals':count}
        d['edges']=[edge('start','fork'),edge('fork','again'),edge('again','fork',2),edge('again','end')]
        compile_graph(d)
        d['edges'].append(edge('again','again'))
        with self.assertRaises(DomainError):compile_graph(d)
    def test_decision_and_condition_branches(self):
        for kind,config,labels in [('human_decision',{'reviewer_roles':['member']},['approved','rejected']),('condition',{'condition':{'field':'x','op':'eq','value':1}},['true','false'])]:
            d=basic();d['nodes'].append(dict(id='decision',type=kind,config=config));d['edges'][0]['to']='decision'
            d['edges'] += [{'from':'decision','to':'end','on':label,'required':True,'max_traversals':0} for label in labels]
            compile_graph(d)
            d['edges'].pop()
            with self.assertRaises(DomainError):compile_graph(d)
    def test_reachability_and_limits(self):
        d=basic();d['nodes'].append(dict(id='orphan',type='end',config={}))
        with self.assertRaises(DomainError):compile_graph(d)
        for count in [-1,101,1.5]:
            d=basic();d['edges'][0]['max_traversals']=count
            with self.assertRaises(DomainError):compile_graph(d)
    def test_literal_fields_and_strict_comparison(self):
        field="__import__('os').system('false')"
        self.assertTrue(evaluate_condition({'field':field,'op':'eq','value':'text'},{field:'text'},[field]))
        self.assertFalse(evaluate_condition({'field':'x','op':'gt','value':0},{'x':True},['x']))
        self.assertFalse(evaluate_condition({'field':'x','op':'eq','value':1},{'x':True},['x']))
        self.assertTrue(evaluate_condition({'field':'x','op':'exists','value':False},{},['x']))
        with self.assertRaises(DomainError):evaluate_condition({'field':'x','op':'in','value':[0]*101},{},['x'])
