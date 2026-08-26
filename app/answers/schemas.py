import json
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Any, Optional


class SourceItem(BaseModel):
    resource_id: Optional[int] = None
    resource_name: str
    page: Any
    chapter: Optional[str] = None


class AnswerResponse(BaseModel):
    id: int
    answer_set_id: int
    question_id: int
    question_number: int
    question_text: str
    marks: int
    content: Optional[str] = None
    sources: Optional[list[dict]] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class AnswerSetResponse(BaseModel):
    id: int
    question_bank_id: int
    user_id: int
    status: str
    total_questions: int
    completed_questions: int
    created_at: datetime
    updated_at: datetime
    answers: list[AnswerResponse] = []

    model_config = {
        "from_attributes": True
    }


class AnswerSetProgressResponse(BaseModel):
    id: int
    question_bank_id: int
    status: str
    total_questions: int
    completed_questions: int
    progress_percentage: float


class GenerateAnswerSetRequest(BaseModel):
    question_bank_id: int
    user_id: Optional[int] = None


class SingleQuestionGenerateRequest(BaseModel):
    question_id: int
    user_id: Optional[int] = None


class RetryAnswerRequest(BaseModel):
    # Optional free-text guidance the user adds when regenerating a single
    # answer. Merged on top of the existing RAG logic; never replaces it.
    user_instruction: Optional[str] = None
