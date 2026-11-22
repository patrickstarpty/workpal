"""Interpret go test -json without accepting TestMain's exit-zero skips."""


def summarize_go_test(events, exit_code):
    running, packages, passed_packages = set(), set(), set()
    executed_packages = set()
    passed = skipped = failed = 0
    errors = []
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get('Package'), str):
            errors.append('malformed Go test event')
            continue
        package, action, test = event['Package'], event.get('Action'), event.get('Test')
        packages.add(package)
        if test:
            key = (package, test)
            if action == 'run':
                if key in running:
                    errors.append('duplicate active test')
                running.add(key)
                executed_packages.add(package)
            elif action in ('pass', 'skip', 'fail'):
                if key not in running:
                    errors.append('terminal test event without execution')
                running.discard(key)
                passed += action == 'pass'
                skipped += action == 'skip'
                failed += action == 'fail'
        elif action == 'pass':
            passed_packages.add(package)
        elif action in ('skip', 'fail'):
            skipped += action == 'skip'
            failed += action == 'fail'
    if type(exit_code) is not int or exit_code != 0:
        errors.append('Go process did not exit successfully')
    if not passed or skipped or failed or running:
        errors.append('tests absent, skipped, failed or unfinished')
    if not packages or packages != executed_packages or packages != passed_packages:
        errors.append('one or more packages lack executed passing tests')
    return {'status': 'failed' if errors else 'passed', 'exit_code': exit_code,
            'passed': passed, 'skipped': skipped, 'failed': failed, 'errors': errors}
