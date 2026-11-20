import re
from django.core.exceptions import ValidationError
CATEGORIES = ['backlog','todo','in_progress','in_review','done','blocked','cancelled']
def obj(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)
def string(maximum):
    return dict(type='string', minLength=1, maxLength=maximum)
DEFINITION = obj(dict(
    states=dict(type='array', minItems=2, maxItems=100, items=obj(dict(key=string(64),label=string(100),category=dict(type='string',enum=CATEGORIES)))),
    transitions=dict(type='array',maxItems=1000,items=obj({'from':string(64),'to':string(64)})),
    review_policy=obj(dict(completion=dict(type='string',enum=['manual','approved_delivery','approved_head_merged']),reviewer_roles=dict(type='array',minItems=1,maxItems=3,items=dict(type='string',enum=['owner','admin','member']))))))
def validate_definition(value):
    keys = [s['key'] for s in value['states']]
    edges = [(e['from'],e['to']) for e in value['transitions']]
    roles = value['review_policy']['reviewer_roles']
    if (len(set(keys)) != len(keys) or any(not re.fullmatch('[a-z][a-z0-9_]*', k) for k in keys)
        or any(not state['label'].strip() for state in value['states'])
        or not {'backlog','done'} <= {s['category'] for s in value['states']}
        or len(set(edges)) != len(edges) or any(a not in keys or b not in keys for a,b in edges)
        or len(set(roles)) != len(roles)):
        raise ValidationError('Invalid definition.')
def default_definition():
    edges = list(zip(CATEGORIES[:4], CATEGORIES[1:5])) + [('in_review','in_progress')]
    edges += [(s,t) for s in CATEGORIES[:4] for t in ('blocked','cancelled')]
    edges += [('blocked','todo'),('cancelled','backlog')]
    return dict(states=[dict(key=k,label=k.replace('_',' ').title(),category=k) for k in CATEGORIES],transitions=[{'from':a,'to':b} for a,b in edges],review_policy=dict(completion='approved_head_merged',reviewer_roles=['owner','admin']))
