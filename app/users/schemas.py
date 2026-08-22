from datetime import datetime
from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=100)
    name: str = Field(min_length=1, max_length=100)


class UserLogin(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserProfileResponse(BaseModel):
    id: int
    username: str
    name: str
    has_openai_key: bool
    has_gemini_key: bool
    has_groq_key: bool
    has_cerebras_key: bool
    has_nvidia_key: bool
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse


class OpenAIKeyUpdate(BaseModel):
    openai_api_key: str = Field(min_length=1)


class GeminiKeyUpdate(BaseModel):
    gemini_api_key: str = Field(min_length=1)


class GroqKeyUpdate(BaseModel):
    groq_api_key: str = Field(min_length=1)


class CerebrasKeyUpdate(BaseModel):
    cerebras_api_key: str = Field(min_length=1)


class NvidiaKeyUpdate(BaseModel):
    nvidia_api_key: str = Field(min_length=1)


# Backward compatibility schemas
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    openai_api_key: str | None = None


class UserResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }