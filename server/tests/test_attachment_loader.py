import pytest
from workpal_backend.projects.access import Hidden

A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
U='cccccccc-cccc-cccc-cccc-cccccccccccc'
P='dddddddd-dddd-dddd-dddd-dddddddddddd'

class Queries:
    def __init__(self, *, failure='', workspace=W, bound=False):
        self.failure=failure;self.calls=[]
        self.row={'id':A,'workspace_id':workspace,'issue_id':P if bound else None,'comment_id':None}
    def call(self,kind,*args):
        self.calls.append((kind,*args))
        if self.failure==kind:raise RuntimeError('database unavailable')
    def get_attachment(self,identity,workspace):self.call('scoped',identity,workspace);return self.row
    def get_attachment_by_id(self,identity):self.call('attachment',identity);return self.row
    def get_member(self,workspace,user):self.call('member',workspace,user);return {}
    def issue_project(self,identity):self.call('project',identity);return P

class Cache:
    def __init__(self,hit=False):self.hit=hit;self.calls=[]
    def get(self,*args):self.calls.append(('get',*args));return self.hit
    def set(self,*args):self.calls.append(('set',*args))

def loader(q, cache=None, hidden=None):
    from workpal_backend.files.loader import AttachmentLoader
    return AttachmentLoader(q, membership_cache=cache, hidden_projects=hidden or (lambda workspace: Hidden()))

def assert_error(status,message,fn):
    from workpal_backend.files.loader import AttachmentLoadError
    with pytest.raises(AttachmentLoadError) as caught:fn()
    assert (caught.value.status,caught.value.message)==(status,message)

@pytest.mark.parametrize(('workspace','identity','message'),[('','bad','workspace_id is required'),('bad','bad','invalid attachment id'),('bad',A,'invalid workspace id')])
def test_request_validation_precedes_database(workspace,identity,message):
    q=Queries()
    assert_error(400,message,lambda:loader(q).for_request(identity,workspace))
    assert q.calls==[]

@pytest.mark.parametrize('download',[False,True])
def test_lookup_errors_are_not_found(download):
    q=Queries(failure='attachment' if download else 'scoped');l=loader(q)
    assert_error(404,'attachment not found',lambda:l.for_download(A,U) if download else l.for_request(A,W))


def test_download_auth_is_checked_after_lookup_and_before_workspace():
    q=Queries(workspace=None)
    assert_error(401,'user not authenticated',lambda:loader(q).for_download(A,''))
    assert q.calls==[('attachment',A)]
    assert_error(404,'attachment not found',lambda:loader(q).for_download(A,U))


def test_download_membership_denial_is_indistinguishable_from_missing():
    q=Queries(failure='member');cache=Cache()
    assert_error(404,'attachment not found',lambda:loader(q,cache).for_download(A,U))
    assert cache.calls==[('get',U,W)]


def test_download_caches_membership_before_private_project_denial():
    q=Queries(bound=True);cache=Cache();hidden=Hidden();hidden.add([P])
    assert_error(404,'attachment not found',lambda:loader(q,cache,lambda w:hidden).for_download(A,U))
    assert cache.calls==[('get',U,W),('set',U,W)]
    assert q.calls==[('attachment',A),('member',W,U),('project',P)]


def test_cache_hit_still_enforces_project_visibility():
    q=Queries(bound=True);hidden=Hidden();hidden.add([P]);cache=Cache(True)
    assert_error(404,'attachment not found',lambda:loader(q,cache,lambda w:hidden).for_download(A,U))
    assert q.calls==[('attachment',A),('project',P)]
    assert cache.calls==[('get',U,W)]


def test_unbound_attachment_skips_project_lookup():
    def unexpected(workspace):raise AssertionError('must not query private projects')
    q=Queries();cache=Cache(True)
    assert loader(q,cache,unexpected).for_download(A,U)==q.row
    assert loader(q,cache,unexpected).for_request(A,W)==q.row

@pytest.mark.parametrize('failure',['hidden','project'])
def test_project_resolution_failure_returns_500(failure):
    q=Queries(bound=True,failure=failure);hidden=Hidden();hidden.add([P])
    def get_hidden(workspace):
        if failure=='hidden':raise RuntimeError('database unavailable')
        return hidden
    assert_error(500,'failed to resolve project access',lambda:loader(q,hidden=get_hidden).for_request(A,W))


def test_invalid_user_on_cache_miss_denies_without_member_query():
    q=Queries()
    assert_error(404,'attachment not found',lambda:loader(q).for_download(A,'invalid'))
    assert q.calls==[('attachment',A)]


@pytest.mark.parametrize(('stage','status'), [('hidden',499),('project',500)])
def test_only_hidden_project_query_uses_request_cancellation_response(stage,status):
    import asyncio
    from workpal_backend.files.loader import AttachmentLoader
    q=Queries(bound=True);hidden=Hidden();hidden.add([P])
    def get_hidden(workspace):
        if stage=='hidden':raise asyncio.CancelledError()
        return hidden
    def project(identity):raise asyncio.CancelledError()
    q.issue_project=project
    l=AttachmentLoader(q, hidden_projects=get_hidden, request_error=lambda:asyncio.CancelledError())
    assert_error(status,'' if status==499 else 'failed to resolve project access',lambda:l.for_request(A,W))
