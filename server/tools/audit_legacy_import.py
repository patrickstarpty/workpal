"""Run with the project Python environment; exit nonzero on unproven integrity."""
import argparse
import json
from workpal_backend.legacy_audit import audit

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--expected-checksum')
    args = parser.parse_args()
    result = audit(args.source, args.target, expected_checksum=args.expected_checksum)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result['ok'] else 1)
