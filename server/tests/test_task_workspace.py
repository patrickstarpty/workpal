"""Task-token target selection contracts derived from actual Go middleware tests."""
from fastapi import HTTPException
from starlette.requests import Request
import pytest
from workpal_backend.auth.task_workspace import check_target

A='aaaaaaaa-1111-2222-3333-444444444444'
B='bbbbbbbb-1111-2222-3333-444444444444'


def request(query='', headers=()):
    return Request({'type':'http','method':'POST','path':'/api/upload-file',
                    'query_string':query.encode(),'headers':[(k.lower().encode(),v.encode()) for k,v in headers]})


def lookup(slug):
    if slug=='error': raise OSError('offline')
    return {'ws-a':A,'ws-b':B}.get(slug)


@pytest.mark.parametrize('query,headers', [
    ('',[]), ('workspace_id='+A,[]), ('workspace_id=',[]),
    ('workspace_slug=ws-a',[]), ('workspace_slug=ws%2Da&q=a%20b',[]),
    ('workspace_id='+A+'&workspace_slug=ws-a',[('X-Workspace-ID',A.upper())]),
    ('',[('X-Workspace-Slug','ws-a'),('X-Workspace-Slug','ws-a')]),
    ('workspace_id='+A.replace('-',''),[]),
])
def test_all_selectors_must_match(query,headers):
    check_target(request(query,headers), A, lookup)


@pytest.mark.parametrize('query,headers,status,error', [
    ('workspace_id='+B,[],403,'task token is bound to a different workspace'),
    ('workspace_id='+A+'&workspace_id='+B,[],403,'task token is bound to a different workspace'),
    ('',[('X-Workspace-ID',A),('X-Workspace-ID',B)],403,'task token is bound to a different workspace'),
    ('workspace_slug=ws-b',[],403,'task token is bound to a different workspace'),
    ('workspace_slug=ws-a&workspace_slug=ws-b',[],403,'task token is bound to a different workspace'),
    ('workspace_id=nope',[],400,'invalid workspace_id'),
    ('workspace_slug=unknown',[],404,'workspace not found'),
    ('workspace_slug=error',[],500,'failed to resolve workspace'),
    ('workspace_id='+A+'&q=%zz',[],400,'malformed query string'),
    ('workspace_slug=ws-a;ignored=1',[],400,'malformed query string'),
    ('workspace_id='+B+'%zz',[],400,'malformed query string'),
    ('q=%',[],400,'malformed query string'),
    ('q=%0',[],400,'malformed query string'),
])
def test_conflicts_and_malformed_queries(query,headers,status,error):
    with pytest.raises(HTTPException) as exc:
        check_target(request(query,headers),A,lookup)
    assert (exc.value.status_code,exc.value.detail)==(status,error)


def test_selector_order_and_cached_slug_resolution():
    calls=[]
    def resolve(slug):
        calls.append(slug)
        return A
    check_target(request('workspace_slug=ws-a',[('X-Workspace-Slug','ws-a')]),A,resolve)
    assert calls==['ws-a']
    with pytest.raises(HTTPException) as exc:
        check_target(request('workspace_id='+B,[('X-Workspace-ID','invalid')]),A,resolve)
    assert exc.value.detail=='invalid workspace_id'
