import asyncio
import pytest


class QueryError(Exception):
    def __init__(self,code):self.sqlstate=code


def wrapped(error):
    outer=RuntimeError('operation failed')
    outer.__cause__=error
    return outer


@pytest.mark.parametrize(('parent','error','direct','query'),[
    (asyncio.CancelledError(),asyncio.CancelledError(),True,True),
    (None,asyncio.CancelledError(),False,False),
    (TimeoutError(),asyncio.CancelledError(),False,False),
    (asyncio.CancelledError(),TimeoutError(),False,False),
    (asyncio.CancelledError(),RuntimeError('unavailable'),False,False),
    (asyncio.CancelledError(),wrapped(asyncio.CancelledError()),True,True),
    (asyncio.CancelledError(),QueryError('57014'),False,True),
    (None,QueryError('57014'),False,False),
    (asyncio.CancelledError(),wrapped(QueryError('57014')),False,True),
    (asyncio.CancelledError(),QueryError('08006'),False,False),
    (asyncio.CancelledError(),None,False,False),
])
def test_cancellation_requires_parent_and_matching_operation(parent,error,direct,query):
    from workpal_backend.infrastructure.request_cancellation import is_request_cancellation,is_query_cancellation
    assert is_request_cancellation(parent,error)==direct
    assert is_query_cancellation(parent,error)==query


def test_implicit_exception_context_is_not_an_explicit_wrapped_cause():
    from workpal_backend.infrastructure.request_cancellation import is_request_cancellation
    outer=RuntimeError('unrelated')
    outer.__context__=asyncio.CancelledError()
    assert not is_request_cancellation(asyncio.CancelledError(),outer)


def test_joined_error_and_empty_cancellation_response():
    from workpal_backend.infrastructure.request_cancellation import cancellation_response
    error=BaseExceptionGroup('write failed',[BrokenPipeError(),asyncio.CancelledError()])
    response=cancellation_response(asyncio.CancelledError(),error)
    assert response.status_code==499
    assert response.body==b''
    assert cancellation_response(None,error) is None
