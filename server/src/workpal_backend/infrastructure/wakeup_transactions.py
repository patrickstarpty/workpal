"""Canonical transaction-local attribution and caller-owned query execution.

The providers must implement real transaction settings and commit/rollback;
this module does not simulate PostgreSQL row locks on another database.
"""
from asyncio import CancelledError

_ACTOR_SQL = "SELECT set_config('workpal.actor_type',$1,true),set_config('workpal.actor_id',$2,true),set_config('workpal.source_task_id',$3,true)"
_HANDOFF_SQL = "SELECT set_config('workpal.handed_to_agent',$1,true)"


class WakeupTransactions:
    def __init__(self, begin, queries_for, *, actor=None, handed_to=''):
        self.begin = begin
        self.queries_for = queries_for
        self.actor = actor
        self.handed_to = handed_to

    def run(self, operation):
        transaction = self.begin()
        try:
            if self.actor is not None:
                transaction.execute(_ACTOR_SQL, self.actor)
            if self.handed_to:
                transaction.execute(_HANDOFF_SQL, (self.handed_to,))
            queries = self.queries_for(transaction)
            result = operation(queries)
            transaction.commit()
            return result
        finally:
            # Go defers Rollback even after Commit and ignores rollback errors.
            try:
                transaction.rollback()
            except (Exception, CancelledError):
                pass

