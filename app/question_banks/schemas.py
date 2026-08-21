from datetime import datetime

from pydantic import BaseModel, Field
from typing import Literal


# Safe representation of a stored question bank.
class QuestionBankResponse(BaseModel):
    id: int
    user_id: int
    name: str
    subject: str
    cloudinary_url: str
    resource_ids: str
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


# Representation of an extracted question.
class QuestionResponse(BaseModel):
    id: int
    question_bank_id: int
    question_number: int
    question_text: str
    marks: int
    marks_source: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


# Response model used when returning multiple questions.
class QuestionListResponse(BaseModel):
    questions: list[QuestionResponse]
