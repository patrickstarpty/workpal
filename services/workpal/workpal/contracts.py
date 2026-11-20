from dataclasses import dataclass, field
from uuid import uuid4

@dataclass(frozen=True)
class Actor:
    user_id: int
    workspace_id: int | None
    executor_id: str | None = None
    session_id: str | None = None

@dataclass(frozen=True)
class ObjectRef:
    kind: str
    id: str

@dataclass(frozen=True)
class SubjectRef:
    type: str
    id: str

@dataclass
class ActionRequest:
    action_id: str
    payload: dict
    expected_revision: int | None
    idempotency_key: str | None
    confirmation_id: str | None = None

@dataclass
class ActionResult:
    state: str
    object_refs: list
    data: dict
    error: object = None

class DomainError(Exception):
    def __init__(self, code, message, request_id=None, retryable=False, details=None, status=400):
        self.code, self.message = code, message
        self.request_id = request_id or str(uuid4())
        self.retryable, self.details, self.status = retryable, details or {}, status
        super().__init__(message)

@dataclass
class DataScope:
    workspace_id: int
    source_refs: set

@dataclass
class PublicationPayload:
    id: str
    source_refs: set
    destination: str
    content_hash: str
    content_ref: ObjectRef
    revision: int
    status: str

@dataclass
class EventEnvelope:
    id: str
    workspace_id: int
    aggregate_ref: ObjectRef
    sequence: int
    type: str
    payload: dict
    created_at: object
