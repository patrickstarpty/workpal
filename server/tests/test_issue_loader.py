import asyncio
import pytest
from workpal_backend.projects.access import Hidden
from workpal_backend.infrastructure.query_errors import NoRows
I='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';P='cccccccc-cccc-cccc-cccc-cccccccccccc'
class Queries:
    def __init__(self):self.calls=[];self.failure='';self.prefix='ABC';self.project=None;self.denied=False
    def record(self,kind,*args):
        self.calls.append((kind,*args))
        if self.failure==kind:raise NoRows()
        if self.failure==kind+'-cancel':raise asyncio.CancelledError()
    def get_workspace(self,identity):self.record('workspace',identity);return dict(name='A2b-c world',issue_prefix=self.prefix)
    def get_issue_by_number(self,workspace,number):self.record('number',workspace,number);return dict(id=I,workspace_id=W,project_id=self.project)
    def get_issue_in_workspace(self,identity,workspace):self.record('issue',identity,workspace);return dict(id=I,workspace_id=W,project_id=self.project)
    def hidden(self,workspace):
        self.record('hidden',workspace);hidden=Hidden()
        if self.denied:hidden.add([P])
        return hidden

def load(q,identity=I,user='user',workspace=W,cancelled=False):
    from workpal_backend.issues.loader import IssueLoader
    return IssueLoader(q,hidden_projects=q.hidden,request_error=lambda:asyncio.CancelledError() if cancelled else None).for_user(identity,user,workspace)

def expect_error(q,status,**kwargs):
    from workpal_backend.issues.loader import IssueLoadError
    with pytest.raises(IssueLoadError) as caught:load(q,**kwargs)
    assert caught.value.status==status
    return caught.value.message

@pytest.mark.parametrize('user,workspace,status',[('','',401),('user','',400)])
def test_auth_precedes_workspace_and_issue_validation(user,workspace,status):
    q=Queries();expect_error(q,status,identity='bad',user=user,workspace=workspace);assert q.calls==[]

@pytest.mark.parametrize('identity',['abc-42','ABC-00042'])
def test_identifier_lookup_uses_workspace_prefix_and_skips_uuid_lookup(identity):
    q=Queries();assert load(q,identity)['id']==I
    assert q.calls==[('workspace',W),('number',W,42)]


def test_legacy_workspace_prefix_uses_name_ascii_letters_not_slug():
    q=Queries();q.prefix='';assert load(q,'abc-1')['id']==I

@pytest.mark.parametrize('identity',['bad','ABC-0','ABC--1','ABC-2147483648','ABC-１２','-1','ABC-+1','ABC-1 '])
def test_invalid_or_mismatching_identifier_is_not_found(identity):
    q=Queries();assert expect_error(q,404,identity=identity)=='issue not found'
    assert not any(call[0] in ('number','issue') for call in q.calls)


def test_uuid_with_numeric_tail_can_probe_workspace_before_uuid_lookup():
    q=Queries();identity='aaaaaaaa-aaaa-aaaa-aaaa-000000000001'
    load(q,identity)
    assert q.calls==[('workspace',W),('issue',identity,W)]


def test_valid_uuid_with_invalid_workspace_returns_specific_400():
    q=Queries();assert expect_error(q,400,workspace='bad')=='invalid workspace_id';assert q.calls==[]

@pytest.mark.parametrize('failure,identity,status',[('workspace','ABC-1',404),('number','ABC-1',404),('issue',I,404),('hidden',I,500)])
def test_query_errors_and_visibility_errors_have_original_responses(failure,identity,status):
    q=Queries();q.failure=failure;q.project=P;expect_error(q,status,identity=identity)

@pytest.mark.parametrize('operation,identity',[('workspace','ABC-1'),('number','ABC-1'),('issue',I),('hidden',I)])
def test_only_parent_request_cancellation_maps_to_499(operation,identity):
    q=Queries();q.failure=operation+'-cancel';q.project=P
    expect_error(q,499,identity=identity,cancelled=True)
    expect_error(q,500 if operation=='hidden' else 404,identity=identity)


def test_private_project_is_indistinguishable_from_missing_issue():
    q=Queries();q.project=P;q.denied=True
    assert expect_error(q,404)=='issue not found'
