"""Immutable transport facts; identity and capability reports grant no permission."""
from dataclasses import dataclass, field
from datetime import datetime

@dataclass(frozen=True)
class CapabilityReport:
    provider_key: str
    version: int
    installed: bool
    authenticated: bool
    execution_ready: bool

@dataclass(frozen=True)
class TaskIdentity:
    runtime_id: int
    workspace_id: int
    run_id: int
    epoch: int
    token_id: int

@dataclass(frozen=True)
class Lease:
    run_id: int
    epoch: int
    expires_at: datetime
    input_snapshot: dict
    task_token: str
    allowed_actions: tuple[str, ...] = field(default=(), init=False)

@dataclass(frozen=True)
class Renewal:
    run_id: int
    epoch: int
    expires_at: datetime
    task_token: str

@dataclass(frozen=True)
class Renewed:
    lease: Renewal
    kind: str = field(default='renewed', init=False)

@dataclass(frozen=True)
class StopOnly:
    run_id: int
    epoch: int
    reason: str
    kind: str = field(default='stop_only', init=False)

@dataclass(frozen=True)
class Denied:
    code: str
    status: int
    kind: str = field(default='denied', init=False)

@dataclass(frozen=True)
class ClaimResult:
    lease: Lease | None
