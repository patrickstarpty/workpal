"""Canonical request-vs-operation cancellation classification.

Callers supply the actual parent-request error. A timeout or an independently
cancelled operation must not be reported as client cancellation.
"""
import asyncio
from starlette.responses import Response


def _errors(error):
    stack = [error]
    seen = set()
    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        if isinstance(current, BaseExceptionGroup):
            stack.extend(reversed(current.exceptions))
        elif current.__cause__ is not None:
            stack.append(current.__cause__)


def _cancelled(error):
    return any(isinstance(value, asyncio.CancelledError) for value in _errors(error))


def is_request_cancellation(parent_error, operation_error):
    return _cancelled(parent_error) and _cancelled(operation_error)


def is_query_cancellation(parent_error, operation_error):
    if is_request_cancellation(parent_error, operation_error):
        return True
    if not _cancelled(parent_error):
        return False
    # Go errors.As selects the first PostgreSQL error, even when its code
    # does not match. Do not search past it for another matching SQLSTATE.
    for error in _errors(operation_error):
        if hasattr(error, 'sqlstate'):
            return error.sqlstate == '57014'
    return False


def cancellation_response(parent_error, operation_error, *, query=False):
    predicate = is_query_cancellation if query else is_request_cancellation
    return Response(status_code=499) if predicate(parent_error, operation_error) else None
