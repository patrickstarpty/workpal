from dataclasses import dataclass
@dataclass(frozen=True)
class ActionSpec:
    action_id: str
    form_class: type
    output_schema: dict
    handler: object
    resolve_refs: object
    capability: str = 'read'
    allowed_roles: tuple = ('owner','admin','member')
    mutating: bool = False
    confirmation_required: bool = False
    compensation: str | None = None
    audit_fields: tuple = ()
    revision_required: bool = False
    result_refs: object = None
