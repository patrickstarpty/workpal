"""Delete a live comment under canonical issue/comment/receipt locks.

The caller authorizes the request and supplies WakeupTransactions with actual
transaction-bound queries. Object cleanup and events belong after commit.
"""
from ..infrastructure.query_errors import NoRows


class TaskSupplementInFlight(RuntimeError):
    def __init__(self):
        super().__init__('additional message is still being delivered')


class CommentDeletion:
    def __init__(self, transactions):
        self.transactions = transactions

    def delete(self, comment_id, workspace_id):
        return self.transactions.run(lambda queries: self._delete(queries, comment_id, workspace_id))

    def _delete(self, queries, comment_id, workspace_id):
        target = queries.lock_comment_for_delete(comment_id, workspace_id)
        receipts = queries.lock_task_supplements_by_comment(comment_id, workspace_id)
        if any(receipt['status'] in ('pending', 'delivering') for receipt in receipts):
            raise TaskSupplementInFlight()
        if receipts:
            queries.delete_task_supplement_by_comment(comment_id, workspace_id)
        identity, workspace = target['id'], target['workspace_id']
        has_replies = queries.comment_has_replies(identity, workspace)
        urls = queries.delete_comment_attachments(identity, workspace)
        queries.delete_comment_reactions(identity, workspace)
        result = dict(tombstone=None, removed_ids=None, attachment_urls=urls, issue_revision=0)
        if has_replies:
            result['tombstone'] = queries.tombstone_comment(identity, workspace)
            queries.settle_delegated_failure_recovery_comment(identity)
        else:
            removed = queries.delete_leaf_comment(identity, workspace)
            result['removed_ids'] = [removed['id']]
            parent = removed.get('parent_id')
            for _ in range(256):
                if parent is None:
                    break
                try:
                    pruned = queries.delete_replyless_comment_tombstone(parent, workspace)
                except NoRows:
                    break
                result['removed_ids'].append(pruned['id'])
                parent = pruned.get('parent_id')
        try:
            result['issue_revision'] = queries.touch_issue_for_comment_delete(target['issue_id'], workspace)
        except NoRows:
            pass
        return result
