import pytest
from workpal_backend.projects.access import Hidden
from workpal_backend.infrastructure.query_errors import NoRows

P='00000000-0000-0000-0000-000000000001'
Q='00000000-0000-0000-0000-000000000002'
I='00000000-0000-0000-0000-000000000003'
C='00000000-0000-0000-0000-000000000004'


class Queries:
    def __init__(self,result=P,failure=None):self.result=result;self.failure=failure;self.calls=[]
    def get(self,kind,identity):
        self.calls.append((kind,identity))
        if self.failure:raise self.failure
        return self.result
    def issue_project(self,identity):return self.get('issue',identity)
    def comment_project(self,identity):return self.get('comment',identity)


def hidden():
    value=Hidden();value.add([P]);return value


@pytest.mark.parametrize(('attachment','calls','expected'),[
    ({'issue_id':I,'comment_id':C},[('issue',I)],True),
    ({'issue_id':None,'comment_id':C},[('comment',C)],True),
    ({'chat_session_id':I,'task_id':C},[],False),
    ({},[],False),
])
def test_issue_takes_precedence_over_comment(attachment,calls,expected):
    from workpal_backend.files.access import attachment_in_hidden_project
    q=Queries()
    assert attachment_in_hidden_project(q,hidden(),attachment)==expected
    assert q.calls==calls


def test_empty_hidden_set_does_not_load_attachment_parent():
    from workpal_backend.files.access import attachment_in_hidden_project
    q=Queries(failure=RuntimeError('unavailable'))
    assert not attachment_in_hidden_project(q,Hidden(),{'issue_id':I})
    assert q.calls==[]


def test_missing_parent_is_not_hidden_but_lookup_errors_propagate():
    from workpal_backend.files.access import attachment_in_hidden_project
    assert not attachment_in_hidden_project(Queries(failure=NoRows()),hidden(),{'issue_id':I})
    with pytest.raises(RuntimeError):attachment_in_hidden_project(Queries(failure=RuntimeError()),hidden(),{'issue_id':I})
    assert not attachment_in_hidden_project(Queries(result=None),hidden(),{'issue_id':I})


def test_filter_keeps_input_order_duplicates_and_missing_ids():
    from workpal_backend.files.access import visible_attachment_ids
    class Lookup(Queries):
        def list_attachments_by_ids(self,workspace,ids):
            assert workspace=='workspace' and ids==['hidden','visible','missing','hidden','visible']
            return [{'id':'hidden','issue_id':I},{'id':'visible'}]
    ids=['hidden','visible','missing','hidden','visible']
    assert visible_attachment_ids(Lookup(),hidden(),'workspace',ids)==['visible','missing','visible']
    assert ids==['hidden','visible','missing','hidden','visible']
