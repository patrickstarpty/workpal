"""Run Go struct decoding and Python decoding on identical isolated fixtures.

This proves decoding cases only, never HTTP/auth/SQL/event equivalence.
Go request structs are extracted verbatim from the protected source.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'server/src'))
from workpal_backend.workspaces.decode import decode_create, decode_update, decode_pin


def run(output):
    source_path = ROOT / 'server/go/internal/handler/workspace.go'
    source = source_path.read_text()
    declarations = [re.search(r'type ' + name + r' struct \{.*?\n\}', source, re.S).group()
                    for name in ('CreateWorkspaceRequest', 'UpdateWorkspaceRequest')]
    pin = re.search(r'func \(h \*Handler\) SetWorkspacePinned.*?var req struct \{(.*?)\n\t\}', source, re.S).group(1)
    program = 'package main\nimport("encoding/json";"os";"strings")\n' + '\n'.join(declarations)
    program += '\ntype PinRequest struct {' + pin + '\n}\n'
    program += '''
type Case struct { Kind string `json:"kind"`; Raw string `json:"raw"` }
func main() {
 var cases []Case
 if err := json.NewDecoder(os.Stdin).Decode(&cases); err != nil { panic(err) }
 results := make([]any, 0, len(cases))
 for _, c := range cases {
  var value any
  switch c.Kind {case "create": value=&CreateWorkspaceRequest{}; case "update": value=&UpdateWorkspaceRequest{}; case "pin": value=&PinRequest{}; default: panic("unknown case")}
  err := json.NewDecoder(strings.NewReader(c.Raw)).Decode(value)
  if err != nil {results=append(results,map[string]any{"error":"invalid request body"})} else {results=append(results,map[string]any{"value":value})}
 }
 if err := json.NewEncoder(os.Stdout).Encode(results); err != nil {panic(err)}
}
'''
    cases_path = ROOT / 'server/tests/parity/cases/workspace_decode.json'
    cases = json.loads(cases_path.read_text())
    with tempfile.TemporaryDirectory(prefix='workpal-decode-parity-') as directory:
        Path(directory, 'main.go').write_text(program)
        base = ['docker','run','--rm','--network','none','-v',f'{directory}:/case','-w','/case']
        version = subprocess.check_output(base + ['golang:1.26.9','go','version'], text=True).strip()
        if 'go1.26.9 ' not in version:
            raise RuntimeError('reference toolchain mismatch')
        subprocess.run(base + ['-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off',
            '-e','GOFLAGS=','golang:1.26.9','go','build','-mod=readonly','-o','reference','main.go'], check=True)
        command = ['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{directory}:/case:ro',
            'sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/case/reference']
        process = subprocess.run(command, input=json.dumps(cases), text=True, capture_output=True, check=True)
    go = json.loads(process.stdout)
    python = []
    for case in cases:
        try:
            value = {'create':decode_create, 'update':decode_update, 'pin':decode_pin}[case['kind']](case['raw'].encode())
            if case['kind'] == 'pin': value = {'pinned':value}
            python.append({'value':value})
        except ValueError:
            python.append({'error':'invalid request body'})
    mismatches = [i for i in range(len(cases)) if go[i] != python[i]]
    evidence = dict(scope='workspace request decoding only; not endpoint parity', toolchain=version,
        target='linux/amd64 CGO_ENABLED=0 GOWORK=off GOFLAGS= tags=[] mod=readonly',
        source_sha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
        fixtures_sha256=hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        cases=cases, go=go, python=python, mismatches=mismatches, exit_code=process.returncode)
    Path(output).write_text(json.dumps(evidence, ensure_ascii=True, indent=2) + '\n')
    print(f'{len(cases)} decoding cases; mismatches: {mismatches}')
    return bool(mismatches)


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1]))
