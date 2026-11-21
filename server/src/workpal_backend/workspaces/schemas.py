"""Go create input accepts unknown fields but never accepts body identity."""
from pydantic import BaseModel, StrictStr

class CreateWorkspace(BaseModel):
    name: StrictStr
    slug: StrictStr
    issue_prefix: StrictStr | None = None

class UpdateWorkspace(BaseModel):
    name: StrictStr | None = None
    description: StrictStr | None = None
    context: StrictStr | None = None
    issue_prefix: StrictStr | None = None
    avatar_url: StrictStr | None = None
    settings: object = None
    repos: object = None
