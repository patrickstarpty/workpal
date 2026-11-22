import pytest
from .normalization import compare_observations


def capture():
    return {'status':200,'headers':{'content-type':'application/json'},'body':{'id':'go-id','value':None},'events':[],'state':{},'external_calls':[]}

@pytest.mark.parametrize('field,value',[('status',201),('body',{'id':'go-id'}),('body',{'id':'go-id','value':[]}),('events',[{'type':'created'}]),('external_calls',[{'method':'send'}])])
def test_observable_difference_cannot_disappear(field,value):
    left=capture();right=capture();right[field]=value
    assert compare_observations(left,right)

def test_explicit_random_id_mapping_preserves_shape():
    left=capture();right=capture();right['body']['id']='python-id'
    rules=[{'path':['body','id'],'go':'go-id','python':'python-id','token':'created-id','kind':'identifier'}]
    assert compare_observations(left,right,rules)==[]
    right['body'].pop('value')
    assert compare_observations(left,right,rules)

def test_normalization_does_not_hide_wrong_reference():
    left=capture();right=capture();right['body']['id']='wrong'
    rules=[{'path':['body','id'],'go':'go-id','python':'python-id','token':'created-id','kind':'identifier'}]
    assert compare_observations(left,right,rules)

def test_boolean_is_not_integer():
    left=capture();right=capture();left['body']['value']=True;right['body']['value']=1
    assert compare_observations(left,right)

def test_missing_normalized_field_rejected():
    left=capture();right=capture();right['body'].pop('id')
    assert compare_observations(left,right,[{'path':['body','id'],'go':'go-id','python':'python-id','token':'id','kind':'identifier'}])

def test_capture_requires_all_observation_channels():
    assert compare_observations({'status':200},{'status':200})

def test_input_capture_is_not_mutated():
    left=capture();right=capture();right['body']['id']='python-id'
    compare_observations(left,right,[{'path':['body','id'],'go':'go-id','python':'python-id','token':'id','kind':'identifier'}])
    assert left['body']['id']=='go-id' and right['body']['id']=='python-id'

def test_status_normalization_is_never_allowed():
    left=capture();right=capture();right['status']=500
    assert compare_observations(left,right,[{'path':['status'],'go':200,'python':500,'token':'status','kind':'identifier'}])

def test_one_logical_id_cannot_map_to_multiple_references():
    left=capture();right=capture();right['body']['id']='python-id'
    left['body']['parent_id']='parent';right['body']['parent_id']='other'
    rules=[{'path':['body','id'],'go':'go-id','python':'python-id','token':'same','kind':'identifier'}, {'path':['body','parent_id'],'go':'parent','python':'other','token':'same','kind':'identifier'}]
    assert compare_observations(left,right,rules)
