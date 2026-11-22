from workpal_backend.infrastructure.database import Database, migrate

def test_restart_and_fencing(settings):
    from workpal_backend.infrastructure.jobs import schedule, claim, finish
    migrate(settings)
    db = Database(settings)
    with db.transaction() as s:
        schedule(s, 'files.reconcile', now=10)
        first = claim(s, now=10, lease_seconds=2)
    db.close()
    db = Database(settings)
    with db.transaction() as s:
        assert claim(s, now=11) is None
        second = claim(s, now=13)
        assert not finish(s, first, now=13, interval=10)
        assert finish(s, second, now=13, interval=10)
        assert claim(s, now=14) is None
    db.close()

def test_two_connections_and_busy(settings):
    import time
    import pytest
    from sqlalchemy import text
    from workpal_backend.infrastructure.database import DatabaseBusy
    from workpal_backend.infrastructure.jobs import schedule, claim
    migrate(settings)
    a, b = Database(settings), Database(settings)
    try:
        with a.transaction() as s: schedule(s, 'files.reconcile', now=1)
        with a.transaction() as s: assert claim(s, now=1)
        with b.transaction() as s: assert claim(s, now=1) is None
        with a.transaction() as s:
            s.execute(text('UPDATE scheduled_jobs SET due=0'))
            start = time.monotonic()
            with pytest.raises(DatabaseBusy):
                with b.transaction() as other: claim(other, now=1)
            assert time.monotonic()-start < 2
    finally:
        a.close()
        b.close()


def test_simultaneous_claim_and_expired_owner_fencing(settings):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from workpal_backend.infrastructure.jobs import schedule, claim, finish
    migrate(settings)
    db = Database(settings)
    with db.transaction() as s: schedule(s, 'files.reconcile', now=10)
    barrier = Barrier(2)
    def contender():
        connection = Database(settings)
        try:
            barrier.wait(timeout=5)
            with connection.transaction() as s: return claim(s, now=10, lease_seconds=1)
        finally: connection.close()
    try:
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: contender(), range(2)))
        winners = [r for r in results if r]
        assert len(winners) == 1
        with db.transaction() as s:
            replacement = claim(s, now=12)
            assert replacement['token'] != winners[0]['token']
            assert not finish(s, winners[0], now=12, interval=1, error=RuntimeError('stale'))
            assert finish(s, replacement, now=12, interval=1)
    finally: db.close()


def test_signal_shutdown_restores_handlers(settings, monkeypatch):
    import signal
    import pytest
    from workpal_backend import worker
    migrate(settings)
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
        calls = []
        def cleanup(*args, **kwargs):
            calls.append(1)
            signal.raise_signal(sig)
        monkeypatch.setattr(worker, 'reconcile_expired', cleanup)
        worker.run(settings)
        assert calls == [1]
        assert all(signal.getsignal(s) == handler for s, handler in previous.items())
        # Make the persisted schedule due for the second signal run.
        from sqlalchemy import text
        db = Database(settings)
        with db.transaction() as s: s.execute(text('UPDATE scheduled_jobs SET due=0'))
        db.close()
