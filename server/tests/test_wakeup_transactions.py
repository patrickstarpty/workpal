from test_attachment_write_transactions import Tx


def test_shared_transaction_returns_callback_value_and_attributes_before_write():
    from workpal_backend.infrastructure.wakeup_transactions import WakeupTransactions
    log=[];query=object()
    def begin():log.append(('begin',));return Tx(log)
    def write(q):assert q is query;log.append(('write',));return 'result'
    result=WakeupTransactions(begin,lambda tx:query,actor=('agent','agent','task'),handed_to='recipient').run(write)
    assert result=='result'
    assert [entry[0] for entry in log]==['begin','execute','execute','write','commit','rollback']
