"""CLI-owned scheduler. Bounded outbox delivery; no external execution."""
import logging
import signal
from threading import Event
from .infrastructure.database import Database, DatabaseBusy
from .infrastructure.delivery import OutboxDelivery
from .infrastructure.jobs import schedule, claim, finish
from .files.storage import LocalBlobStore
from .files.reconcile import reconcile_expired

log = logging.getLogger(__name__)

def run(settings):
    stop = Event()
    previous = {sig: signal.signal(sig, lambda *_: stop.set()) for sig in (signal.SIGTERM, signal.SIGINT)}
    database = None
    delivery = None
    try:
        database = Database(settings)
        if database.readiness() != 'ok': raise RuntimeError('Run migrations before worker')
        root = settings.upload_dir
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        store = LocalBlobStore(root)
        delivery = OutboxDelivery(settings)
        registry = {'files.reconcile': lambda: reconcile_expired(database, store, should_stop=stop.is_set)}
        while not stop.is_set():
            try:
                delivery.dispatch(database, should_stop=stop.is_set)
                if stop.is_set(): break
                with database.transaction() as session:
                    schedule(session, 'files.reconcile')
                    job = claim(session)
                if job:
                    error = None
                    try:
                        if job['name'] not in registry: raise ValueError('Unknown job: '+job['name'])
                        registry[job['name']]()
                    except Exception as exc:
                        error = exc
                        log.exception('Scheduled job failed')
                    with database.transaction() as session:
                        finish(session, job, interval=settings.reconcile_interval, error=error)
            except DatabaseBusy:
                log.warning('Scheduler database busy; retrying')
            stop.wait(settings.worker_poll_interval)
    finally:
        try:
            try:
                if delivery is not None: delivery.close()
            finally:
                if database is not None: database.close()
        finally:
            for sig, handler in previous.items(): signal.signal(sig, handler)
