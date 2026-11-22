import pytest
from workpal_backend.infrastructure.query_errors import NoRows
from test_attachment_write_transactions import Tx


def row(issue=None,comment=None):
    return dict(id='attachment',workspace_id='workspace',issue_id=issue,comment_id=comment)

class Queries:
    def __init__(self,log,fresh,failure):self.log,self.fresh,self.failure=log,fresh,failure
    def call(self,name,*args):
        self.log.append((name,*args))
        if name==self.failure:raise NoRows()
        return self.fresh
    def lock_issue_for_attachment_write(self,*args):return self.call('issue',*args)
    def lock_live_comment(self,*args):return self.call('comment',*args)
    def get_attachment(self,*args):return self.call('read',*args)
    def lock_attachment_row(self,*args):return self.call('row',*args)


def invoke(initial,fresh,log,failure=''):
    from workpal_backend.files.write_transactions import AttachmentWriter
    states=iter(fresh)
    def begin():
        log.append(('begin',))
        return Tx(log,'commit' if failure=='commit' else '')
    writer=AttachmentWriter(begin,lambda tx:Queries(log,next(states),failure))
    def write(queries):
        log.append(('write',))
        if failure=='write':raise RuntimeError('write failed')
        return 'deleted'
    return writer.with_owner_lock(initial,write)


def test_unowned_attachment_locks_its_row_and_commits_before_release():
    log=[]
    assert invoke(row(),[row()],log)=='deleted'
    assert log==[('begin',),('row','attachment','workspace'),('write',),('commit',),('rollback',)]


def test_owner_change_releases_old_locks_and_retries_issue_before_comment():
    log=[]
    assert invoke(row(),[row('issue','comment'),row('issue','comment')],log)=='deleted'
    assert log==[('begin',),('row','attachment','workspace'),('rollback',),('begin',),
        ('issue','issue','workspace'),('comment','comment','workspace'),('read','attachment','workspace'),
        ('write',),('commit',),('rollback',)]


def test_three_owner_changes_abort_without_mutation():
    log=[]
    with pytest.raises(RuntimeError,match='attachment owner kept changing under the lock'):
        invoke(row(),[row('1'),row('2'),row('3')],log)
    assert [entry[0] for entry in log].count('begin')==3
    assert [entry[0] for entry in log].count('rollback')==3
    assert ('write',) not in log and ('commit',) not in log


def test_missing_issue_still_checks_attachment_after_cascade():
    log=[]
    assert invoke(row('issue'),[row('issue')],log,'issue')=='deleted'
    assert [entry[0] for entry in log]==['begin','issue','read','write','commit','rollback']

@pytest.mark.parametrize('failure',['comment','read','row','write','commit'])
def test_failed_lock_read_write_or_commit_rolls_back_and_never_retries(failure):
    log=[];initial=row() if failure=='row' else row('issue','comment')
    with pytest.raises((NoRows,RuntimeError)):
        invoke(initial,[initial],log,failure)
    assert log[-1]==('rollback',)
    assert [entry[0] for entry in log].count('begin')==1
    if failure in ('comment','read','row'):assert ('write',) not in log
