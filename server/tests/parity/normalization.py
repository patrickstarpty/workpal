"""Compare full observations, allowing only explicit scalar substitutions.

Cases must name exact paths and expected values from both runtimes. No field
removal, wildcard paths or broad timestamp/identifier rewriting is supported.
"""
from copy import deepcopy

CHANNELS = {'status', 'headers', 'body', 'events', 'state', 'external_calls'}


def compare_observations(go, python, rules=()):
    errors = []
    for name, capture in [('Go', go), ('Python', python)]:
        if not isinstance(capture, dict) or not CHANNELS.issubset(capture):
            errors.append(f'{name}: missing observation channels')
    if errors:
        return errors
    left, right = deepcopy(go), deepcopy(python)
    paths = set()
    tokens = {}
    for rule in rules:
        try:
            path = tuple(rule['path'])
            if not path or path in paths or not isinstance(rule['token'], str) or not rule['token']:
                raise ValueError('empty or duplicate normalization')
            leaf = path[-1]
            kind = rule['kind']
            if path[0] not in ('body', 'state', 'events') or not isinstance(leaf, str):
                raise ValueError('normalization outside payload identifiers/timestamps')
            if kind == 'identifier':
                if not (leaf == 'id' or leaf.endswith('_id')) or not all(isinstance(rule[k], str) for k in ('go', 'python')):
                    raise ValueError('identifier field required')
            elif kind == 'timestamp':
                if leaf not in ('created_at', 'updated_at', 'deleted_at', 'timestamp', 'started_at', 'finished_at', 'occurred_at'):
                    raise ValueError('timestamp field required')
            else:
                raise ValueError('unsupported normalization kind')
            pair = (kind, rule['go'], rule['python'])
            if rule['token'] in tokens and tokens[rule['token']] != pair:
                raise ValueError('inconsistent reference mapping')
            tokens[rule['token']] = pair
            paths.add(path)
            for capture, name in [(left, 'go'), (right, 'python')]:
                parent = capture
                for part in path[:-1]:
                    parent = parent[part]
                actual = parent[path[-1]]
                expected = rule[name]
                if isinstance(actual, (dict, list)) or type(actual) is not type(expected) or actual != expected:
                    raise ValueError('normalization value mismatch')
                # An object marker prevents collision with a literal payload string.
                parent[path[-1]] = {'$parity_scalar': rule['token']}
        except (KeyError, IndexError, TypeError, ValueError):
            errors.append('Invalid normalization: exact scalar path/value required')
    if errors:
        return errors

    def compare(a, b, path):
        if type(a) is not type(b):
            errors.append(f'{path}: value types differ')
        elif isinstance(a, dict):
            if a.keys() != b.keys():
                errors.append(f'{path}: fields differ')
            for key in a.keys() & b.keys():
                compare(a[key], b[key], f'{path}.{key}')
        elif isinstance(a, list):
            if len(a) != len(b):
                errors.append(f'{path}: array lengths differ')
            for i, (av, bv) in enumerate(zip(a, b)):
                compare(av, bv, f'{path}[{i}]')
        elif a != b:
            errors.append(f'{path}: values differ')
    compare(left, right, '$')
    return errors
