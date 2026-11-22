"""Attachment writes using the canonical wakeup transaction protocol.

The caller supplies a real transaction factory and transaction-bound queries.
execute accepts Go/Postgres positional SQL and a tuple of parameters. This
module does not emulate row locks or transaction-local settings on SQLite.
"""
from ..infrastructure.query_errors import NoRows

from ..infrastructure.wakeup_transactions import WakeupTransactions


class AttachmentWriter(WakeupTransactions):
    def _write(self, params, *, live_comment):
        def operation(queries):
            if live_comment:
                queries.lock_live_comment(params['comment_id'], params['workspace_id'])
            return queries.create_attachment(params)
        return self.run(operation)

    def with_owner_lock(self, attachment, write):
        for attempt in range(3):
            def operation(queries):
                issue, comment = attachment.get('issue_id'), attachment.get('comment_id')
                workspace = attachment['workspace_id']
                if issue is not None:
                    try:
                        queries.lock_issue_for_attachment_write(issue, workspace)
                    except NoRows:
                        pass
                if comment is not None:
                    queries.lock_live_comment(comment, workspace)
                read = queries.get_attachment if issue is not None or comment is not None else queries.lock_attachment_row
                fresh = read(attachment['id'], workspace)
                if fresh.get('issue_id') != issue or fresh.get('comment_id') != comment:
                    raise _OwnerChanged(fresh)
                return write(queries)
            try:
                return self.run(operation)
            except _OwnerChanged as error:
                attachment = error.attachment
                if attempt == 2:
                    raise RuntimeError('attachment owner kept changing under the lock') from None

    def create(self, params):
        return self._write(params, live_comment=False)

    def create_for_live_comment(self, params):
        return self._write(params, live_comment=True)


class _OwnerChanged(Exception):
    def __init__(self, attachment):
        self.attachment = attachment
