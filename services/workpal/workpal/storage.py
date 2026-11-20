import time
from django.db import transaction, OperationalError
from workpal.contracts import DomainError

MAX_SQLITE_INTEGER = 2**63 - 1

def atomic_write(operation):
    """Run local database work only. Callers must perform network I/O outside this callback."""
    for attempt in range(3):
        try:
            with transaction.atomic():
                return operation()
        except OperationalError as exc:
            if not any(word in str(exc).lower() for word in ("locked", "busy")):
                raise DomainError("storage_unavailable", "Storage unavailable.", retryable=True, status=503) from exc
            if attempt == 2:
                raise DomainError("storage_busy", "Storage busy. Retry later.", retryable=True, status=503) from exc
            time.sleep((.05, .15)[attempt])
