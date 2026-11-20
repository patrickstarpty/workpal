"""Public graph persistence DTOs."""
from typing import TypedDict
from .graph_contracts import GraphSnapshot

class GraphDraftSummary(TypedDict):
    id: int
    name: str
    revision: int
    current_version_id: int

class GraphDraftView(GraphDraftSummary):
    definition: dict

class NodeInputs(TypedDict):
    node_id: str
    agent_id: int
    input_refs: list[dict]

class GraphVersionView(TypedDict):
    id: int
    draft_id: int
    number: int
    name: str
    graph: GraphSnapshot
    published_by: int
    published_at: str
    resolved_inputs: list[NodeInputs]

class InstanceSnapshot(TypedDict):
    schema_version: int
    graph_version: GraphVersionView
    issue: dict
    requirements: dict
    agents: list[dict]
    source_refs: list[dict]
    created_by: int

class GraphInstanceView(TypedDict):
    id: int
    version_id: int
    subject: dict
    state: str
    snapshot: InstanceSnapshot
    sha256: str
    created_at: str

class GraphInstanceSummary(TypedDict):
    id: int
    version_id: int
    subject: dict
    state: str
    sha256: str
    created_at: str
