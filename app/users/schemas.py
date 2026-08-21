from datetime import datetime

from pydantic import BaseModel, Field

# Data required to create a new AcademicStack user.
class UserCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    openai_api_key: str = Field(
        min_length=1,
    )

# Safe user representation returned by the API. API keys are intentionally NOT included.
class UserResponse(BaseModel):
    id: int 
    name: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }