"""Explicit invocation only; Task7 owns scheduling."""
import time
from .repository import claim_expired, complete_cleanup, fail_cleanup, StaleLease

def reconcile_expired(database, store, now=None, limit=100, *, should_stop=None):
    clock = time.time if now is None else lambda: now
    counts = dict(claimed=0, completed=0, failed=0, stale=0)
    if should_stop is not None and should_stop():
        return counts
    with database.transaction() as session:
        claims = claim_expired(session, clock(), limit)
    counts['claimed'] = len(claims)
    for claim in claims:
        # Leave skipped claims leased; restart reclaims them after expiry.
        if should_stop is not None and should_stop():
            break
        error = None
        try:
            store.delete_owned(claim['storage_key'], claim['staging_key'], ready=True)
        except Exception as exc:
            error = exc
        try:
            with database.transaction() as session:
                if error is None: complete_cleanup(session, claim, now=clock())
                else: fail_cleanup(session, claim, error, now=clock())
            counts['completed' if error is None else 'failed'] += 1
        except StaleLease:
            counts['stale'] += 1
    return counts
