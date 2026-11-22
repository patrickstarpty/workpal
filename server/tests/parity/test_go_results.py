import pytest
from .go_results import summarize_go_test


def event(action, test=None):
    result={'Action':action,'Package':'reference/pkg'}
    if test:result['Test']=test
    return result


def test_real_executed_test_passes():
    report=summarize_go_test([event('run','TestContract'),event('pass','TestContract'),event('pass')],0)
    assert report['status']=='passed' and report['passed']==1

@pytest.mark.parametrize('events,code',[
    ([event('pass')],0),
    ([event('run','TestContract'),event('skip','TestContract'),event('pass')],0),
    ([event('run','TestContract'),event('fail','TestContract'),event('fail')],1),
    ([event('run','TestContract')],0),
    ([event('pass','TestContract'),event('pass')],0),
    ([event('run','TestContract'),event('pass','TestContract'),event('pass')],1),
    ([event('run','TestContract'),event('pass','TestContract')],0),
])
def test_false_green_rejected(events,code):
    assert summarize_go_test(events,code)['status']!='passed'


def test_testmain_skip_cannot_pass_with_exit_zero():
    events=[event('output')|{'Output':'Skipping integration tests: database not reachable\n'},event('pass')]
    assert summarize_go_test(events,0)['status']!='passed'
