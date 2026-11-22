"""Privacy reference precedence must preserve null versus missing."""
import pytest
from workpal_backend.realtime.event_refs import extract_event_refs

@pytest.mark.parametrize('kind,payload,expected',[
 ('project:updated',{'project':{'id':'nested'},'project_id':'top'},{'project_known':True,'project_id':'nested'}),
 ('issue:updated',{'issue':{'project_id':None,'id':'issue'},'issue_id':'other'},{'project_known':True}),
 ('issue:updated',{'issue':{'project_id':42,'id':'issue'}},{'issue_id':'issue'}),
 ('issue:deleted',{'project_id':'project','issue_id':'issue'},{'project_known':True,'project_id':'project'}),
 ('unknown',{'project_id':'project','issue_id':'issue'},{'issue_id':'issue'}),
 ('project_folder:filed',{'project_id':'project'},{'project_known':True,'project_id':'project'}),
 ('autopilot:changed',{'autopilot':{'project_id':None},'autopilot_id':'auto'},{'project_known':True}),
 ('autopilot:changed',{'autopilot_id':'auto','issue_id':'issue'},{'autopilot_id':'auto'}),
 ('comment:updated',{'comment':{'id':'c','issue_id':'i'},'comment_id':'other'},{'issue_id':'i'}),
 ('comment:deleted',{'comment':{'id':'c','issue_id':None},'comment_id':'other'},{'comment_id':'c'}),
 ('pull_request:updated',{'linked_issue_ids':['i',None,23,'j',{},True]},{'linked_issue_ids':['i','','','j','','']}),
 ('pull_request:updated',{'linked_issue_ids':[]},{'linked_issue_ids':[]}),
 ('unknown',{'linked_issue_ids':42},{}),
 ('unknown',['not','object'],{}),
 ('unknown',{'issue_id':'i','bad':float('nan')},{}),
])
def test_reference_projection(kind,payload,expected):
    defaults=dict(project_known=False,project_id='',issue_id='',comment_id='',autopilot_id='',linked_issue_ids=None)
    defaults.update(expected)
    assert vars(extract_event_refs(kind,payload))==defaults


def test_extension_registration_is_explicit_and_not_prefix_wildcard():
    assert extract_event_refs('custom:event',{'project_id':'p'}).project_known is False
    assert extract_event_refs('custom:event',{'project_id':'p'},project_events={'custom:event'}).project_id=='p'
    assert extract_event_refs('project_folder:other',{'project_id':'p'}).project_known is False
