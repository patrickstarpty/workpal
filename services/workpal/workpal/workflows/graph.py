"""Pure, closed workflow definitions and non-executable conditions."""
import hashlib
import json
import re
from workpal.contracts import DomainError
from .graph_contracts import GraphSnapshot


def _fail(code):
    raise DomainError(code, 'Invalid graph definition' if code == 'invalid_graph' else 'Invalid condition', status=400)


def _json(value, code):
    def visit(v, depth=0):
        if depth > 32: _fail(code)
        if type(v) is str:
            try: v.encode('utf-8')
            except UnicodeError: _fail(code)
            return
        if v is None or type(v) in (bool, int): return
        if type(v) is float:
            import math
            if math.isfinite(v): return
        if type(v) is list:
            for x in v: visit(x, depth+1)
            return
        if type(v) is dict and all(type(k) is str for k in v):
            for k, x in v.items():
                visit(k, depth+1); visit(x, depth+1)
            return
        _fail(code)
    visit(value)
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError):
        _fail(code)


def _fields(fields, code):
    if type(fields) is not list or len(fields)>100 or any(type(f) is not str or not f for f in fields) or len(set(fields)) != len(fields): _fail(code)


def _condition(c, fields):
    code='invalid_condition'
    _json(fields,code); _fields(fields,code); _json(c,code)
    if type(c) is not dict or set(c) not in ({'field','op','value'},{'field','op'}): _fail(code)
    if c.get('field') not in fields or c.get('op') not in ('eq','ne','in','exists','gt','gte','lt','lte'): _fail(code)
    op=c['op']; v=c.get('value')
    if op!='exists' and 'value' not in c: _fail(code)
    if op=='exists' and 'value' in c and type(v) is not bool: _fail(code)
    if op=='in' and (type(v) is not list or len(v)>100): _fail(code)
    if op in ('gt','gte','lt','lte') and type(v) not in (int,float): _fail(code)


def evaluate_condition(condition, values, declared_fields)->bool:
    _condition(condition,declared_fields); _json(values,'invalid_condition')
    if type(values) is not dict: _fail('invalid_condition')
    f=condition['field']; op=condition['op']; v=condition.get('value',True)
    if op=='exists': return (f in values)==v
    if f not in values: return False
    a=values[f]
    def equal(x,y):
        if type(x) in (int,float) and type(y) in (int,float): return x==y
        if type(x) is not type(y): return False
        if type(x) is list: return len(x)==len(y) and all(equal(a,b) for a,b in zip(x,y))
        if type(x) is dict: return x.keys()==y.keys() and all(equal(x[k],y[k]) for k in x)
        return x==y
    if op=='eq': return equal(a,v)
    if op=='ne': return not equal(a,v)
    if op=='in': return any(equal(a,x) for x in v)
    if type(a) not in (int,float): return False
    return {'gt':lambda:a>v,'gte':lambda:a>=v,'lt':lambda:a<v,'lte':lambda:a<=v}[op]()


def compile_graph(definition)->GraphSnapshot:
    code='invalid_graph'
    raw=_json(definition,code); d=json.loads(raw)
    if type(d) is not dict or set(d)!={'nodes','edges','declared_fields'}: _fail(code)
    _fields(d['declared_fields'],code)
    nodes=d['nodes']; edges=d['edges']
    if type(nodes) is not list or not 2<=len(nodes)<=200 or type(edges) is not list or len(edges)>1000: _fail(code)
    by={}
    for n in nodes:
        if type(n) is not dict or set(n)!={'id','type','config'}: _fail(code)
        i=n['id']; t=n['type']; c=n['config']
        if type(i) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,63}',i) or i in by or type(c) is not dict: _fail(code)
        if t in ('start','end','parallel'): valid=not c
        elif t=='join': valid=c=={'mode':'all_required'}
        elif t in ('human_decision','delivery_review'):
            roles=c.get('reviewer_roles'); valid=set(c)=={'reviewer_roles'} and type(roles) is list and bool(roles) and all(type(r) is str and r in ('owner','admin','member') for r in roles) and len(set(roles))==len(roles)
            if valid: c['reviewer_roles']=sorted(roles)
        elif t=='agent_task': valid=set(c)=={'agent_id','input_refs'} and type(c['agent_id']) is int and c['agent_id']>0 and type(c['input_refs']) is list and all(type(x) is str for x in c['input_refs'])
        elif t=='create_child': valid=set(c)=={'title','description'} and type(c['title']) is str and bool(c['title'].strip()) and type(c['description']) is str
        elif t=='condition':
            valid=set(c)=={'condition'}
            if valid:
                try: _condition(c['condition'],d['declared_fields'])
                except DomainError: _fail(code)
        else: valid=False
        if not valid: _fail(code)
        by[i]=n
    incoming={i:[] for i in by}; outgoing={i:[] for i in by}; seen=set()
    for e in edges:
        if type(e) is not dict or set(e)!={'from','to','on','required','max_traversals'}: _fail(code)
        if type(e['from']) is not str or type(e['to']) is not str or e['from'] not in by or e['to'] not in by or e['on'] not in ('always','true','false','approved','rejected') or type(e['required']) is not bool or type(e['max_traversals']) is not int or not 0<=e['max_traversals']<=100: _fail(code)
        key=(e['from'],e['to'],e['on'])
        if key in seen: _fail(code)
        seen.add(key); incoming[e['to']].append(e); outgoing[e['from']].append(e)
    starts=[i for i in by if by[i]['type']=='start']; ends=[i for i in by if by[i]['type']=='end']
    if len(starts)!=1 or not ends: _fail(code)
    for i,n in by.items():
        t=n['type']; out=outgoing[i]; labels=[e['on'] for e in out]
        if t=='start' and incoming[i] or t=='end' and out: _fail(code)
        if t=='condition':
            if sorted(labels)!=['false','true']: _fail(code)
        elif t in ('human_decision','delivery_review'):
            if sorted(labels)!=['approved','rejected']: _fail(code)
        elif any(x!='always' for x in labels) or (len(out)>1 and t!='parallel'): _fail(code)
        if t=='join' and not any(e['required'] for e in incoming[i]): _fail(code)
    def reach(seeds,links,key):
        found=set(seeds); todo=list(seeds)
        while todo:
            for e in links[todo.pop()]:
                j=e[key]
                if j not in found: found.add(j); todo.append(j)
        return found
    if reach(starts,outgoing,'to')!=set(by) or reach(ends,incoming,'from')!=set(by): _fail(code)
    degree={i:sum(e['max_traversals']==0 for e in incoming[i]) for i in by}; todo=[i for i in by if degree[i]==0]; count=0
    while todo:
        i=todo.pop(); count+=1
        for e in outgoing[i]:
            if e['max_traversals']: continue
            degree[e['to']]-=1
            if degree[e['to']]==0: todo.append(e['to'])
    if count!=len(by): _fail(code)
    d['nodes']=sorted(nodes,key=lambda n:n['id']); d['edges']=sorted(edges,key=lambda e:(e['from'],e['to'],e['on'])); d['declared_fields'].sort()
    return {'schema_version':1,'definition':d,'sha256':hashlib.sha256(_json(d,code).encode()).hexdigest()}
