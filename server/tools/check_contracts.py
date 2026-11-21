"""Validate migration evidence without importing the application or its environment."""
import ast
import argparse
import json
import hashlib
import subprocess
import re
from pathlib import Path


PROTECTED_PREFIXES = ('server/go/', 'scripts/', 'docker/', 'deploy/', '.github/workflows/')
PROTECTED_ROOTS = {'Makefile', '.env.example', '.dockerignore', 'package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml'}
PROFILE_FIELDS = ('go_version', 'GOOS', 'GOARCH', 'CGO_ENABLED', 'GOWORK', 'GOFLAGS', 'tags', 'edition', 'module_mode')


def protected_input(name):
    return (name.startswith(PROTECTED_PREFIXES) or name in PROTECTED_ROOTS
            or ('/' not in name and ('Dockerfile' in name or name.startswith('docker-compose'))))


def check_baseline(root: Path, manifest_path: Path, *, profile: dict) -> list[str]:
    """Compare source inputs and declared build profile; does not claim a build ran."""
    errors = []
    try:
        manifest = json.loads(manifest_path.read_text())
        files, expected = manifest.get('files'), manifest.get('build_profile')
        if not isinstance(files, dict) or not files:
            return ['baseline: missing protected files']
        if not isinstance(expected, dict) or not isinstance(profile, dict):
            return ['baseline: missing build profile']
        for field in PROFILE_FIELDS:
            if field not in expected or field not in profile or expected[field] != profile[field]:
                errors.append(f'baseline: build profile mismatch: {field}')
        listed = subprocess.run(['git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                                check=True, capture_output=True).stdout.decode().split('\0')
        discovered = {name for name in listed if name and protected_input(name)}
        recorded = set(files)
        for name in sorted(discovered - recorded):
            errors.append(f'baseline: unrecorded input: {name}')
        for name in sorted(recorded):
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts or not protected_input(name):
                errors.append(f'baseline: invalid protected path: {name}')
                continue
            path = root / relative
            if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
                errors.append(f'baseline: unsafe input: {name}')
            elif name not in discovered or not path.is_file():
                errors.append(f'baseline: missing input: {name}')
            elif hashlib.sha256(path.read_bytes()).hexdigest() != files[name]:
                errors.append(f'baseline: changed input: {name}')
    except (OSError, ValueError, AttributeError, TypeError, subprocess.SubprocessError):
        errors.append('baseline: unreadable manifest or source enumeration failed')
    return errors


def check_handler_binding(root: Path, route: dict) -> list[str]:
    """Validate explicit source bindings, never search globally by method name.

    This is declaration validation, not proof of the route registration's type.
    The Go registration audit must supply and validate the binding separately.
    """
    binding = route.get('handler_binding')
    if binding is None:
        return []
    label = f"{route.get('method')} {route.get('path')}: handler binding"
    try:
        if not isinstance(binding, dict): return [f'{label}: malformed']
        source = binding['source']
        path, line = source.rsplit(':', 1)
        relative = Path(path)
        if not path.startswith('server/go/') or relative.is_absolute() or '..' in relative.parts or path.endswith('_test.go'):
            return [f'{label}: invalid production source']
        package = 'workpal.local/workpal/server/' + str(relative.parent.relative_to('server/go'))
        if package != binding['package']:
            return [f'{label}: package mismatch']
        lines = (root / relative).read_text().splitlines()
        number = int(line)
        declaration = lines[number - 1] if 0 < number <= len(lines) else ''
        pattern = (r'^func \(\w+ \*' + re.escape(binding['receiver']) + r'\) '
                   + re.escape(binding['method']) + r'\(\w+ http.ResponseWriter, \w+ \*http.Request\)')
        if not re.match(pattern, declaration):
            return [f'{label}: receiver/method/signature mismatch']
        fixtures = route.get('fixtures', {})
        candidates = fixtures.get('source_handlers', []) if isinstance(fixtures, dict) else []
        if candidates and any(not isinstance(c, dict) or c.get('source') != source for c in candidates):
            return [f'{label}: conflicting source handler candidates']
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return [f'{label}: unreadable binding']
    return []


def check_contracts(routes_path: Path, callers_path: Path, *, require_complete: bool) -> list[str]:
    errors, seen = [], set()
    try:
        routes = json.loads(routes_path.read_text())
        calls = json.loads(callers_path.read_text())
    except (OSError, ValueError) as exc:
        return [f'inventory unreadable: {exc}']
    producer_coverage = routes.get('producer_coverage') if isinstance(routes, dict) else None
    producers = routes.get('producers', []) if isinstance(routes, dict) else []
    routes = routes.get('routes') if isinstance(routes, dict) else routes
    if isinstance(calls, dict):
        coverage = calls.get('coverage', {})
        if not isinstance(coverage, dict) or coverage.get('complete') is not True:
            errors.append('frontend source coverage incomplete')
    calls = calls.get('calls') if isinstance(calls, dict) else calls
    if not isinstance(routes, list) or not isinstance(calls, list) or not isinstance(producers, list):
        return ['inventory records must be arrays']
    if not routes or not calls:
        errors.append('empty inventory: routes and frontend calls required')
    root = Path(__file__).resolve().parents[2]
    def references(value, label, test=False):
        if not isinstance(value, list) or not value:
            errors.append(f'{label}: missing evidence references')
            return
        for ref in value:
            match = re.fullmatch(r'([^:]+):(\d+)(?:::(\w+))?', ref) if isinstance(ref, str) else None
            if not match:
                errors.append(f'{label}: invalid evidence reference {ref!r}')
                continue
            path = (root / match[1]).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                errors.append(f'{label}: missing reference file {ref}')
                continue
            try:
                source = path.read_text()
            except (OSError, UnicodeError):
                errors.append(f'{label}: unreadable reference {ref}')
                continue
            lines = source.splitlines()
            if test:
                try:
                    functions = {n.name for n in ast.walk(ast.parse(source)) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                except SyntaxError:
                    functions = set()
                if not path.name.startswith('test_') or not match[3] or not match[3].startswith('test_') or match[3] not in functions:
                    errors.append(f'{label}: reference must name a test function {ref}')
            if not 1 <= int(match[2]) <= len(lines) or (match[3] and not any(re.search(r'\bdef '+re.escape(match[3])+r'\b', line) for line in lines)):
                errors.append(f'{label}: invalid reference target {ref}')
    def decision(value, label):
        if not isinstance(value, dict) or not isinstance(value.get('reason'), str) or not value['reason'].strip():
            errors.append(f'{label}: missing source-backed decision')
        references(value.get('sources') if isinstance(value, dict) else None, label)

    def route_key(value, label):
        method, path = value.get('method'), value.get('path')
        if not isinstance(method, str) or method not in ('GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS') or not isinstance(path, str) or not re.fullmatch(r'/[^?#\s]*', path) or '//' in path:
            errors.append(f'{label}: invalid method/path')
            return None
        return method, path

    if require_complete:
        if not isinstance(producer_coverage, dict) or producer_coverage.get('complete') is not True:
            errors.append('non-HTTP producer coverage incomplete: explicit declaration required')
        decision(producer_coverage, 'producer coverage')
    def event_refs(event, label):
        for field in ('producer', 'transaction', 'consumer'):
            references(event.get(field + '_sources'), f'{label} {field}')

    for producer in producers:
        if not isinstance(producer, dict):
            errors.append('malformed producer record')
            continue
        if not producer.get('id') or producer.get('kind') not in ('scheduled','background','webhook','queue','other'):
            errors.append('producer: missing id or valid kind')
        references(producer.get('sources'), 'producer')
        event = producer.get('event', {})
        if not isinstance(event, dict) or event.get('disposition') not in ('required', 'none'):
            errors.append('producer: missing event disposition')
        elif event.get('disposition') == 'required':
            references(event.get('sources'), 'producer event')
            event_refs(event, 'producer event')
            for field in ('producer', 'type', 'payload', 'scope', 'transaction', 'consumer'):
                if not event.get(field): errors.append(f'producer: missing event {field}')
            if require_complete:
                for field in ('commit_test', 'rollback_test', 'recovery_test'):
                    references([event.get(field)], f'producer {field}', test=True)
        else:
            if not event.get('reason'): errors.append('producer: missing event reason')
            references(event.get('sources'), 'producer event exclusion')
    for route in routes:
        if not isinstance(route, dict):
            errors.append('malformed route record')
            continue
        errors.extend(check_handler_binding(root, route))
        references(route.get('sources'), 'route sources')
        key = route_key(route, 'route')
        if key is None:
            continue
        label = ' '.join(str(v) for v in key)
        if key in seen:
            errors.append(f'duplicate route: {label}')
        seen.add(key)
        for field in ('origin','sources','auth','scope','fixtures','dependencies','batch','status'):
            if not route.get(field):
                errors.append(f'{label}: missing {field}')
        if key[0] not in ('GET', 'HEAD', 'OPTIONS') or 'event' in route:
            event = route.get('event', {})
            if not isinstance(event, dict):
                errors.append(f'{label}: malformed event')
                continue
            if event.get('disposition') not in ('required', 'none'):
                errors.append(f'{label}: missing event disposition')
            elif not event.get('sources') or not event.get('reason'):
                errors.append(f'{label}: missing event evidence')
            elif event['disposition'] == 'required':
                event_refs(event, label)
                for field in ('producer','type','payload','scope','transaction','consumer'):
                    if not event.get(field):
                        errors.append(f'{label}: missing event {field}')
                if require_complete:
                    for field in ('commit_test','rollback_test','recovery_test'):
                        references([event.get(field)], f'{label} {field}', test=True)
                        if not event.get(field):
                            errors.append(f'{label}: missing event {field}')
        if isinstance(route.get('event'), dict):
            references(route['event'].get('sources'), f'{label} event')
        if require_complete:
            if route.get('origin') == 'go' and not route.get('handler_binding'):
                errors.append(f'{label}: missing handler binding')
            references(route.get('tests'), f'{label} tests', test=True)
            if route.get('status') == 'implemented':
                fixtures = route.get('fixtures')
                def response(value, low, high):
                    return isinstance(value, dict) and type(value.get('status')) is int and low <= value['status'] < high and 'body' in value
                if not isinstance(fixtures, dict) or not isinstance(fixtures.get('request'), dict) or not response(fixtures.get('success'), 200, 400) or not isinstance(fixtures.get('errors'), list) or not fixtures['errors'] or not all(response(e, 400, 600) for e in fixtures['errors']):
                    errors.append(f'{label}: concrete request/success/error fixtures required')
            if route.get('status') not in ('implemented','unsupported','retired'):
                errors.append(f'{label}: pending route')
            if not route.get('tests'):
                errors.append(f'{label}: missing tests')
            if route.get('status') in ('unsupported','retired'):
                decision(route.get('decision'), f'{label} scope decision')
    for call in calls:
        if not isinstance(call, dict):
            errors.append('malformed frontend call')
            continue
        target = call.get('route', {})
        if not isinstance(target, dict):
            errors.append('malformed frontend route target')
            continue
        references(call.get('sources'), 'frontend sources')
        key = route_key(target, 'frontend target')
        if call.get('decision') is not None:
            decision(call['decision'], 'frontend decision')
        if key not in seen and not call.get('decision'):
            errors.append(f'unmapped frontend call: {call.get("id")}')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1] / 'contracts'
    parser.add_argument('--routes', type=Path, default=root / 'routes.json')
    parser.add_argument('--callers', type=Path, default=root / 'frontend-calls.json')
    parser.add_argument('--require-complete', action='store_true')
    parser.add_argument('--baseline', type=Path, default=Path(__file__).resolve().parents[2] / 'docs/superpowers/evidence/2026-11-22-go-source-sha256.json')
    parser.add_argument('--build-profile', type=Path, help='JSON build profile captured by the parity runner')
    args = parser.parse_args()
    diagnostics = check_contracts(args.routes, args.callers, require_complete=args.require_complete)
    if args.require_complete:
        try:
            profile = json.loads(args.build_profile.read_text()) if args.build_profile else None
        except (OSError, ValueError):
            profile = None
        diagnostics += check_baseline(Path(__file__).resolve().parents[2], args.baseline, profile=profile)
    print('\n'.join(diagnostics) if diagnostics else 'Contract checks passed')
    raise SystemExit(bool(diagnostics))
