from dataclasses import dataclass

@dataclass(frozen=True)
class ProjectView:
    id: int
    name: str
    description: str
    archived: bool
    revision: int
    created_at: str
    updated_at: str
    workflow_version_id: int = 0
