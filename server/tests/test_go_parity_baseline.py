"""Protect embedded/config inputs and build profile, not just Go source text."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location('checker', Path(__file__).parents[1] / 'tools/check_contracts.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
PROFILE = {'go_version':'1.26.9','GOOS':'linux','GOARCH':'amd64','CGO_ENABLED':'0','GOWORK':'off','GOFLAGS':'','tags':[],'edition':'default !oss including ee','module_mode':'readonly'}

@pytest.fixture
def baseline(tmp_path):
    subprocess.run(['git','init','-q',str(tmp_path)],check=True)
    files = ['server/go/go.mod','server/go/go.sum','server/go/internal/handler/reserved_slugs.json','server/go/internal/handler/attachment_text_preview.json','Makefile','.env.example','scripts/local-env.sh']
    for name in files:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('original')
    subprocess.run(['git','-C',str(tmp_path),'add','.'],check=True)
    manifest={'files':{n:hashlib.sha256((tmp_path/n).read_bytes()).hexdigest() for n in files},'build_profile':PROFILE}
    path=tmp_path/'baseline.json';path.write_text(json.dumps(manifest))
    return tmp_path,path,manifest

def check(baseline, profile=None):
    root,path,_=baseline
    return checker.check_baseline(root,path,profile=PROFILE if profile is None else profile)

def test_valid_baseline(baseline):
    assert check(baseline)==[]

@pytest.mark.parametrize('name',['server/go/go.sum','server/go/internal/handler/reserved_slugs.json','server/go/internal/handler/attachment_text_preview.json','Makefile','.env.example'])
def test_non_go_change_blocks(baseline,name):
    (baseline[0]/name).write_text('changed')
    assert any('changed' in e and name in e for e in check(baseline))

def test_added_and_deleted_inputs_block(baseline):
    root,_,_=baseline
    (root/'server/go/new-resource.json').write_text('{}')
    (root/'server/go/go.sum').unlink()
    errors=check(baseline)
    assert any('unrecorded' in e and 'new-resource.json' in e for e in errors)
    assert any('missing' in e and 'go.sum' in e for e in errors)

@pytest.mark.parametrize('field,value',[('tags',['oss']),('GOFLAGS','-tags=oss'),('go_version','1.26.8'),('GOARCH','arm64')])
def test_profile_drift_blocks(baseline,field,value):
    assert any('profile' in e for e in check(baseline,PROFILE|{field:value}))

def test_secret_not_enumerated(baseline):
    (baseline[0]/'.env').write_text('AUTH_SECRET=private')
    assert check(baseline)==[]

def test_corrupt_baseline_fails_closed(baseline):
    baseline[1].write_text('{')
    assert check(baseline)

def test_missing_profile_not_treated_as_valid(baseline):
    root,path,manifest=baseline
    manifest.pop('build_profile');path.write_text(json.dumps(manifest))
    assert check(baseline)
