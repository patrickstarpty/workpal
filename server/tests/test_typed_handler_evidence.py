import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('checker',Path(__file__).parents[1]/'tools/check_contracts.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

@pytest.fixture
def typed(tmp_path):
    candidate={'registration':'server/go/router.go:1','method':'GET','kind':'method','handler_package':'example/handler','handler':'List','receiver':'*example/handler.Service','source':'server/go/handler.go:10'}
    data=json.dumps({'exit_code':0,'registrations':[candidate]}).encode();(tmp_path/'typed.json').write_bytes(data)
    route={'method':'GET','path':'/items','handler_binding':{'registration_source':candidate['registration'],'kind':'method','package':candidate['handler_package'],'method':'List','receiver':'Service','source':candidate['source'],'audit_artifact':'typed.json','audit_sha256':hashlib.sha256(data).hexdigest()}}
    return tmp_path,route

def test_matching_typed_binding(typed):
    assert checker.check_typed_handler_evidence(*typed)==[]

@pytest.mark.parametrize('field,value',[('method','Delete'),('package','different/package'),('source','server/go/other.go:10'),('receiver','Other'),('kind','factory')])
def test_unproven_binding_rejected(typed,field,value):
    typed[1]['handler_binding'][field]=value
    assert checker.check_typed_handler_evidence(*typed)

def test_http_method_mismatch_rejected(typed):
    typed[1]['method']='DELETE'
    assert checker.check_typed_handler_evidence(*typed)

def test_modified_audit_rejected(typed):
    (typed[0]/'typed.json').write_text('{}')
    assert checker.check_typed_handler_evidence(*typed)

def test_missing_audit_rejected(typed):
    typed[1]['handler_binding'].pop('audit_artifact')
    assert checker.check_typed_handler_evidence(*typed)
