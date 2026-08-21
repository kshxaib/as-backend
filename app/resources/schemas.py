from datetime import datetime

from pydantic import BaseModel, Field

# Safe representation of a stored resource.
class ResourceResponse(BaseModel):
    id: int
    user_id: int
    name: str
    subject: str
    chapters: str | None
    description: str | None
    cloudinary_url: str
    visibility: Literal["private", "community"]
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

# Response model used when returning multiple resources.
class ResourceListResponse(BaseModel):
    resources: list[ResourceResponse]