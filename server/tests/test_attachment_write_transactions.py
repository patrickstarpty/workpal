import pytest
from workpal_backend.infrastructure.query_errors import NoRows

class Tx:
    def __init__(self,log,failure=''):self.log=log;self.failure=failure
    def execute(self,sql,args):
        self.log.append(('execute',sql,args))
        if self.failure=='actor':raise RuntimeError('actor failed')
    def commit(self):
        self.log.append(('commit',))
        if self.failure=='commit':raise RuntimeError('commit failed')
    def rollback(self):self.log.append(('rollback',))
class Queries:
    def __init__(self,log,failure):self.log=log;self.failure=failure
    def lock_live_comment(self,identity,workspace):
        self.log.append(('lock',identity,workspace))
        if self.failure=='lock':raise NoRows()
    def create_attachment(self,params):
        self.log.append(('create',params.copy()))
        if self.failure=='create':raise RuntimeError('create failed')
        return dict(params,issue_revision=1)

def writer(log,failure='',actor=None,handed_to=''):
    from workpal_backend.files.write_transactions import AttachmentWriter
    def begin():
        log.append(('begin',))
        if failure=='begin':raise RuntimeError('begin failed')
        return Tx(log,failure)
    return AttachmentWriter(begin,lambda tx:Queries(log,failure),actor=actor,handed_to=handed_to)


def test_plain_create_commits_then_releases_transaction_via_deferred_rollback():
    log=[];params=dict(id='attachment',workspace_id='workspace')
    assert writer(log).create(params)['issue_revision']==1
    assert [call[0] for call in log]==['begin','create','commit','rollback']


def test_comment_create_checks_live_row_under_same_transaction_before_write():
    log=[];params=dict(id='attachment',workspace_id='workspace',comment_id='comment')
    writer(log).create_for_live_comment(params)
    assert log==[('begin',),('lock','comment','workspace'),('create',params),('commit',),('rollback',)]

@pytest.mark.parametrize('failure',['begin','actor','lock','create','commit'])
def test_failure_rolls_back_without_later_mutation(failure):
    log=[]
    with pytest.raises((RuntimeError,NoRows)):
        writer(log,failure,actor=('member','user','task')).create_for_live_comment(dict(comment_id='comment',workspace_id='workspace'))
    kinds=[call[0] for call in log]
    assert (kinds[-1]=='rollback')==(failure!='begin')
    if failure in ('begin','actor','lock'):assert 'create' not in kinds
    if failure!='commit':assert 'commit' not in kinds


def test_actor_and_handoff_attribution_are_transaction_local_before_mutation():
    log=[]
    writer(log,actor=('agent','agent','task'),handed_to='recipient').create({})
    executions=[call for call in log if call[0]=='execute']
    assert executions==[
        ('execute',"SELECT set_config('workpal.actor_type',$1,true),set_config('workpal.actor_id',$2,true),set_config('workpal.source_task_id',$3,true)",('agent','agent','task')),
        ('execute',"SELECT set_config('workpal.handed_to_agent',$1,true)",('recipient',)),
    ]
    assert [call[0] for call in log]==['begin','execute','execute','create','commit','rollback']
