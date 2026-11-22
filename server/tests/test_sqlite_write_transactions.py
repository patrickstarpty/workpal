from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import text
from workpal_backend.infrastructure.database import Database,migrate,DatabaseBusy
from workpal_backend.infrastructure.wakeup_transactions import WakeupTransactions


def test_write_reservation_precedes_reads_and_releases_on_rollback(settings):
    migrate(settings);db=Database(settings)
    try:
        first=db.begin_write()
        try:
            assert first.session.execute(text('SELECT 1')).scalar()==1
            with pytest.raises(DatabaseBusy):db.begin_write()
        finally:first.rollback()
        next_tx=db.begin_write();next_tx.rollback()
    finally:db.close()


def test_real_write_callback_rollback_preserves_data(settings):
    migrate(settings);db=Database(settings)
    try:
        with db.transaction() as s:s.execute(text('CREATE TABLE write_probe(value INTEGER)'))
        writer=WakeupTransactions(db.begin_write,lambda tx:tx.session)
        def failed(session):
            session.execute(text('INSERT INTO write_probe VALUES (1)'))
            raise RuntimeError('abort')
        with pytest.raises(RuntimeError,match='abort'):writer.run(failed)
        with db.transaction() as s:assert s.execute(text('SELECT count(*) FROM write_probe')).scalar()==0
    finally:db.close()


def test_two_connections_cannot_claim_the_same_work(settings):
    settings=settings.model_copy(update={'busy_timeout_ms':2000})
    migrate(settings);db=Database(settings);other=Database(settings)
    try:
        with db.transaction() as s:
            s.execute(text('CREATE TABLE claim_probe(id INTEGER PRIMARY KEY,owner TEXT)'))
            s.execute(text('INSERT INTO claim_probe VALUES (1,NULL)'))
        barrier=Barrier(2)
        def claim(database,owner):
            barrier.wait(timeout=5)
            return WakeupTransactions(database.begin_write,lambda tx:tx.session).run(lambda s:s.execute(
                text('UPDATE claim_probe SET owner=:owner WHERE id=1 AND owner IS NULL RETURNING id'),{'owner':owner}).scalar())
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(claim,db,'a');b=pool.submit(claim,other,'b')
            results=[a.result(timeout=5),b.result(timeout=5)]
        assert results.count(1)==1 and results.count(None)==1
        with db.transaction() as s:assert s.execute(text('SELECT owner FROM claim_probe')).scalar() in ('a','b')
    finally:other.close();db.close()


def test_actor_settings_visible_to_triggers_and_cleared_before_connection_reuse(settings):
    migrate(settings);db=Database(settings)
    try:
        with db.transaction() as s:
            s.execute(text('CREATE TABLE attribution_probe(value TEXT)'))
            s.execute(text('CREATE TABLE attribution_audit(actor TEXT,task TEXT,handoff TEXT)'))
            s.execute(text("CREATE TRIGGER attribution_capture AFTER INSERT ON attribution_probe BEGIN INSERT INTO attribution_audit VALUES (workpal_setting('workpal.actor_id'),workpal_setting('workpal.source_task_id'),workpal_setting('workpal.handed_to_agent')); END"))
        writer=WakeupTransactions(db.begin_write,lambda tx:tx.session,actor=('agent','actor','task'),handed_to='recipient')
        writer.run(lambda s:s.execute(text("INSERT INTO attribution_probe VALUES ('first')")))
        WakeupTransactions(db.begin_write,lambda tx:tx.session).run(lambda s:s.execute(text("INSERT INTO attribution_probe VALUES ('second')")))
        with db.transaction() as s:
            assert list(s.execute(text('SELECT actor,task,handoff FROM attribution_audit ORDER BY rowid')))==[('actor','task','recipient'),(None,None,None)]
    finally:db.close()


def test_unknown_postgres_statement_is_not_silently_accepted(settings):
    migrate(settings);db=Database(settings);tx=db.begin_write()
    try:
        with pytest.raises(ValueError,match='unsupported transaction statement'):tx.execute('SELECT unsupported()',())
    finally:tx.rollback();db.close()
