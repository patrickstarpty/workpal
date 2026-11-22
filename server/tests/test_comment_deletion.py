import pytest
from workpal_backend.infrastructure.query_errors import NoRows
from workpal_backend.infrastructure.wakeup_transactions import WakeupTransactions
from test_attachment_write_transactions import Tx

class Queries:
    def __init__(self,log,*,replies=False,receipts=(),ancestors=(),failure=''):
        self.log=log;self.replies=replies;self.receipts=receipts;self.ancestors=list(ancestors);self.failure=failure
    def call(self,name,*args):
        self.log.append((name,*args))
        if self.failure==name:raise RuntimeError(name+' failed')
        if self.failure==name+'-missing':raise NoRows()
    def lock_comment_for_delete(self,*args):self.call('lock',*args);return dict(id='comment',workspace_id='workspace',issue_id='issue')
    def lock_task_supplements_by_comment(self,*args):self.call('receipts',*args);return [dict(status=status) for status in self.receipts]
    def delete_task_supplement_by_comment(self,*args):self.call('delete_receipts',*args)
    def comment_has_replies(self,*args):self.call('replies',*args);return self.replies
    def delete_comment_attachments(self,*args):self.call('attachments',*args);return ['object']
    def delete_comment_reactions(self,*args):self.call('reactions',*args)
    def tombstone_comment(self,*args):self.call('tombstone',*args);return dict(id='comment',content='',deleted_at='now')
    def settle_delegated_failure_recovery_comment(self,*args):self.call('settle',*args)
    def delete_leaf_comment(self,*args):self.call('leaf',*args);return dict(id='comment',parent_id='parent')
    def delete_replyless_comment_tombstone(self,*args):
        self.call('prune',*args)
        if not self.ancestors:raise NoRows()
        return self.ancestors.pop(0)
    def touch_issue_for_comment_delete(self,*args):self.call('touch',*args);return 7

def remove(log,**kwargs):
    from workpal_backend.comments.deletion import CommentDeletion
    q=Queries(log,**kwargs)
    def begin():log.append(('begin',));return Tx(log)
    return CommentDeletion(WakeupTransactions(begin,lambda tx:q)).delete('comment','workspace')


def test_comment_with_replies_becomes_tombstone_and_settles_recovery():
    log=[];result=remove(log,replies=True,receipts=['delivered'])
    assert result==dict(tombstone=dict(id='comment',content='',deleted_at='now'),removed_ids=None,attachment_urls=['object'],issue_revision=7)
    assert [c[0] for c in log]==['begin','lock','receipts','delete_receipts','replies','attachments','reactions','tombstone','settle','touch','commit','rollback']


def test_leaf_prunes_only_replyless_tombstone_ancestors_nearest_first():
    log=[];result=remove(log,ancestors=[dict(id='parent',parent_id='grandparent')])
    assert result['removed_ids']==['comment','parent'] and result['tombstone'] is None
    assert [c for c in log if c[0]=='prune']==[('prune','parent','workspace'),('prune','grandparent','workspace')]
    assert log[-3:]==[('touch','issue','workspace'),('commit',),('rollback',)]

@pytest.mark.parametrize('status',['pending','delivering'])
def test_inflight_supplement_blocks_deletion_before_child_changes(status):
    log=[]
    with pytest.raises(RuntimeError,match='additional message is still being delivered'):remove(log,receipts=['delivered',status])
    assert [c[0] for c in log]==['begin','lock','receipts','rollback']

@pytest.mark.parametrize('failure',['lock','receipts','replies','attachments','reactions','tombstone','settle','touch'])
def test_query_failure_rolls_back_without_commit(failure):
    log=[]
    with pytest.raises(RuntimeError,match=failure+' failed'):remove(log,replies=True,failure=failure)
    assert log[-1]==('rollback',) and ('commit',) not in log


def test_missing_issue_after_comment_delete_is_not_an_error():
    log=[];result=remove(log,failure='touch-missing')
    assert result['issue_revision']==0 and ('commit',) in log


def test_tombstone_walk_stops_at_original_256_ancestor_limit():
    log=[];result=remove(log,ancestors=[dict(id='parent',parent_id='parent') for _ in range(300)])
    assert len(result['removed_ids'])==257
    assert sum(c[0]=='prune' for c in log)==256
