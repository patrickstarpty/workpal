from django.test import SimpleTestCase
from workpal.contracts import DomainError
from workpal.workflows.graph import compile_graph, evaluate_condition
from tests.test_graph_definition import basic

class GraphReviewTests(SimpleTestCase):
    def test_recursive_json_equality(self):
        for a,b,expected in [({'flag':True},{'flag':1},False),([False],[0],False),(1,1.0,True),({'a':[1,None]},{'a':[1.0,None]},True),([1,2],[2,1],False)]:
            for op,want,value in [('eq',expected,b),('ne',not expected,b),('in',expected,[b])]:
                with self.subTest(a=a,b=b,op=op):
                    self.assertEqual(evaluate_condition(dict(field='x',op=op,value=value),{'x':a},['x']),want)

    def test_unicode_domain_errors(self):
        for field in ['\ud800','\udfff']:
            d=basic(); d['declared_fields']=[field]
            with self.assertRaises(DomainError): compile_graph(d)
            with self.assertRaises(DomainError): evaluate_condition(dict(field='x',op='eq',value=field),{},['x'])

    def test_non_json_and_hooks(self):
        class Hostile:
            def __eq__(self, other): raise AssertionError('hook executed')
        cycle=[]; cycle.append(cycle)
        for value in [Hostile(),cycle,float('inf'),float('nan'),(1,),{'\ud800':1},10**5000]:
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(DomainError): evaluate_condition(dict(field='x',op='eq',value=value),{},['x'])
        value=0
        for _ in range(33): value=[value]
        with self.assertRaises(DomainError): evaluate_condition(dict(field='x',op='eq',value=value),{},['x'])

    def test_missing_null_and_operators(self):
        for op,v in [('eq',None),('ne',1),('in',[None]),('gt',0),('gte',0),('lt',0),('lte',0)]:
            self.assertFalse(evaluate_condition(dict(field='x',op=op,value=v),{},['x']))
        self.assertTrue(evaluate_condition(dict(field='x',op='eq',value=None),{'x':None},['x']))
        self.assertTrue(evaluate_condition(dict(field='x',op='exists'),{'x':None},['x']))
        for op in ['gt','gte','lt','lte']:
            with self.assertRaises(DomainError): evaluate_condition(dict(field='x',op=op,value=True),{},['x'])
            for value in [True,'1',None,[],{}]:
                self.assertFalse(evaluate_condition(dict(field='x',op=op,value=1),{'x':value},['x']))
        self.assertTrue(evaluate_condition(dict(field='x',op='in',value=[0]*99+[1]),{'x':1},['x']))
        with self.assertRaises(DomainError): evaluate_condition(dict(field='x',op='in',value=[1]*101),{},['x'])

    def test_closed_schema(self):
        import copy
        mutations=[lambda d:d.update(extra=0),lambda d:d['nodes'][0].update(extra=0),lambda d:d['edges'][0].update(extra=0),lambda d:d['nodes'][0].update(id='A'),lambda d:d['nodes'][0].update(type='unknown'),lambda d:d['edges'][0].update(required=1),lambda d:d['edges'][0].update(max_traversals=True),lambda d:d['edges'].append(copy.deepcopy(d['edges'][0])),lambda d:d['nodes'].append(dict(id='orphan',type='end',config={}))]
        for change in mutations:
            d=basic(); change(d)
            with self.assertRaises(DomainError): compile_graph(d)

    def test_all_node_configs_and_exact_branches(self):
        cases=[('agent_task',{'agent_id':1,'input_refs':['ref']},['always']),('create_child',{'title':'Child','description':''},['always']),('parallel',{},['always']),('join',{'mode':'all_required'},['always']),('human_decision',{'reviewer_roles':['owner','member']},['approved','rejected']),('delivery_review',{'reviewer_roles':['admin']},['approved','rejected']),('condition',{'condition':{'field':'x','op':'eq','value':1}},['true','false'])]
        for kind,config,labels in cases:
            d=basic(); d['nodes'].append(dict(id='middle',type=kind,config=config)); d['edges'][0]['to']='middle'
            d['edges'] += [dict(**{'from':'middle','to':'end'},on=label,required=True,max_traversals=0) for label in labels]
            compile_graph(d)
            config['extra']=1
            with self.assertRaises(DomainError): compile_graph(d)
            del config['extra']
            if len(labels)==2:
                d['nodes'].append(dict(id='other',type='end',config={}))
                d['edges'].append(dict(**{'from':'middle','to':'other'},on=labels[0],required=True,max_traversals=0))
                with self.assertRaises(DomainError): compile_graph(d)

    def test_node_field_limits_and_isolation(self):
        d=basic(); d['nodes']=[dict(id='n'+str(i),type='start' if i==0 else 'end' if i==199 else 'agent_task',config={} if i in (0,199) else {'agent_id':1,'input_refs':[]}) for i in range(200)]
        d['edges']=[dict(**{'from':'n'+str(i),'to':'n'+str(i+1)},on='always',required=True,max_traversals=0) for i in range(199)]
        d['declared_fields']=['f'+str(i) for i in range(100)]
        result=compile_graph(d); d['nodes'].reverse(); d['edges'].reverse(); d['declared_fields'].reverse()
        self.assertEqual(result,compile_graph(d))
        result['definition']['nodes'][0]['config']['bad']=1
        self.assertNotEqual(result,compile_graph(d))
        d['declared_fields'].append('overflow')
        with self.assertRaises(DomainError): compile_graph(d)
        d['declared_fields']=[]; d['nodes'].append(dict(id='overflow',type='end',config={}))
        with self.assertRaises(DomainError): compile_graph(d)

    def test_bounded_self_loop_and_no_exit(self):
        d=basic(); d['nodes'].append(dict(id='p',type='parallel',config={})); d['edges'][0]['to']='p'
        d['edges'] += [dict(**{'from':'p','to':target},on='always',required=False,max_traversals=count) for target,count in [('p',100),('end',0)]]
        compile_graph(d)
        d['edges'][1]['max_traversals']=0
        with self.assertRaises(DomainError): compile_graph(d)
        d['edges'][1]['max_traversals']=101
        with self.assertRaises(DomainError): compile_graph(d)
        d['edges'].pop(); d['edges'][1]['max_traversals']=1
        with self.assertRaises(DomainError): compile_graph(d)
