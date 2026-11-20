"""JSON-compatible graph snapshot Interface."""
from typing import TypedDict

class GraphSnapshot(TypedDict):
    schema_version: int
    definition: dict
    sha256: str
