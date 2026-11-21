"""References to test source are not evidence those tests ran."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('checker',Path(__file__).parents[1]/'tools/check_contracts.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

@pytest.fixture
def evidence(tmp_path):
    source=tmp_path/'handler.go';source.write_text('package handler')
    route={'method':'GET','path':'/resource','verification':{'report':'report.json'}}
    report={'exit_code':0,'skipped':0,'status':'passed','command':['parity-runner','resource'],'routes':[{'method':'GET','path':'/resource'}], 'source_hashes':{'handler.go':hashlib.sha256(source.read_bytes()).hexdigest()},'build_profile':{'go_version':'1.26.9','GOOS':'linux','GOARCH':'amd64','CGO_ENABLED':'0','GOWORK':'off','GOFLAGS':'','tags':[],'edition':'default !oss including ee','module_mode':'readonly'}}
    return tmp_path,route,report

def run(evidence):
    root,route,report=evidence
    data=json.dumps(report).encode();(root/'report.json').write_bytes(data)
    route['verification']['sha256']=hashlib.sha256(data).hexdigest()
    return checker.check_execution_evidence(root,route)

def test_valid_execution_record(evidence):
    assert run(evidence)==[]

@pytest.mark.parametrize('field,value',[('exit_code',1),('skipped',1),('status','not_run'),('routes',[]),('command',[]),('source_hashes',{}),('build_profile',{})])
def test_unexecuted_or_partial_record_rejected(evidence,field,value):
    evidence[2][field]=value
    assert run(evidence)

def test_stale_source_rejected(evidence):
    (evidence[0]/'handler.go').write_text('package changed')
    assert run(evidence)

def test_tampered_report_rejected(evidence):
    assert run(evidence)==[]
    (evidence[0]/'report.json').write_text('{}')
    assert checker.check_execution_evidence(evidence[0],evidence[1])

def test_missing_record_rejected(evidence):
    assert checker.check_execution_evidence(evidence[0],{'method':'GET','path':'/resource'})
