"""Final graph limits and closed-config acceptance through the public Interface."""
from copy import deepcopy
from django.test import SimpleTestCase
from workpal.contracts import DomainError
from workpal.workflows.graph import compile_graph
from tests.test_graph_definition import basic


def edge(a, b, count=0, on='always'):
    return {'from': a, 'to': b, 'on': on, 'required': True, 'max_traversals': count}


class GraphDefinitionFinalTests(SimpleTestCase):
    def reject(self, graph):
        with self.assertRaises(DomainError) as caught:
            compile_graph(graph)
        self.assertEqual(caught.exception.status, 400)

    def test_thousand_edges_and_one_valid_extra(self):
        d = basic()
        ids = ['start'] + ['n%d' % i for i in range(46)] + ['end']
        d['nodes'] = [dict(id=i, type='start' if i == 'start' else 'end' if i == 'end' else 'parallel', config={}) for i in ids]
        chain = [(ids[i], ids[i+1]) for i in range(len(ids)-1)]
        pairs = chain + [(a, b) for i, a in enumerate(ids) for b in ids[i+1:] if a != 'start' and (a, b) not in chain]
        d['edges'] = [edge(a, b) for a, b in pairs[:1000]]
        self.assertEqual(len(compile_graph(d)['definition']['edges']), 1000)
        self.assertEqual(len({(e['from'], e['to']) for e in d['edges']}), 1000)
        extra = edge(*pairs[1000])
        # Prove the added edge is legal independently of the size limit.
        control = deepcopy(d)
        control['edges'][-1] = extra
        compile_graph(control)
        d['edges'].append(extra)
        self.reject(d)

    def test_shared_node_cycles_require_each_cycle_bounded(self):
        d = basic()
        d['nodes'] += [dict(id=i, type='parallel', config={}) for i in ('a', 'b', 'c')]
        # Cycles a->b->a and a->b->c->a share both a and b.
        d['edges'] = [edge('start', 'a'), edge('a', 'b'), edge('b', 'a', 1), edge('b', 'c'), edge('c', 'a'), edge('c', 'end')]
        self.reject(d)
        for count in (0, 1, 100, 101):
            with self.subTest(max_traversals=count):
                candidate = deepcopy(d)
                candidate['edges'][4]['max_traversals'] = count
                if count in (1, 100):
                    compile_graph(candidate)
                else:
                    self.reject(candidate)

    def test_all_node_configs_have_closed_typed_validation(self):
        configs = {'start': {}, 'end': {}, 'parallel': {}, 'join': {'mode': 'all_required'}, 'human_decision': {'reviewer_roles': ['member']}, 'delivery_review': {'reviewer_roles': ['admin']}, 'agent_task': {'agent_id': 1, 'input_refs': ['x']}, 'create_child': {'title': 'Child', 'description': ''}, 'condition': {'condition': {'field': 'x', 'op': 'eq', 'value': 1}}}
        for kind, config in configs.items():
            d = basic()
            target = kind if kind in ('start', 'end') else 'subject'
            if target == 'subject':
                d['nodes'].append(dict(id=target, type=kind, config=deepcopy(config)))
                d['edges'] = [edge('start', target)]
                labels = ['approved', 'rejected'] if kind in ('human_decision', 'delivery_review') else ['true', 'false'] if kind == 'condition' else ['always']
                d['edges'] += [edge(target, 'end', on=label) for label in labels]
            compile_graph(d)
            variants = [('extra', dict(config, extra=1)), ('not_mapping', []), ('null', None)]
            variants += [('missing_' + key, {k: v for k, v in config.items() if k != key}) for key in config]
            variants += [('wrong_' + key, dict(config, **{key: None})) for key in config]
            if 'reviewer_roles' in config:
                variants += [('roles', {'reviewer_roles': roles}) for roles in ([], ['guest'], ['member', 'member'], [True], 'member')]
            if kind == 'agent_task':
                variants += [('agent_id', dict(config, agent_id=v)) for v in (True, 0, '1')]
                variants += [('input_refs', dict(config, input_refs=v)) for v in ('x', [1], [True])]
            if kind == 'create_child':
                variants += [('title', dict(config, title=v)) for v in ('', '  ', False)]
            if kind == 'condition':
                variants += [('condition', {'condition': c}) for c in ({'field': 'x', 'op': 'eval', 'value': 1}, {'field': 'unknown', 'op': 'eq', 'value': 1}, {'field': [], 'op': 'eq', 'value': 1}, {'field': 'x', 'op': 'in', 'value': 1}, {'field': 'x', 'op': 'exists', 'value': 1}, {'field': 'x', 'op': 'eq'}, {'field': 'x', 'op': 'eq', 'value': 1, 'extra': 1})]
            for label, invalid in variants:
                with self.subTest(node_type=kind, mutation=label, config=invalid):
                    candidate = deepcopy(d)
                    next(n for n in candidate['nodes'] if n['id'] == target)['config'] = invalid
                    self.reject(candidate)
