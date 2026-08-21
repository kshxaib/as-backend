from pydantic import BaseModel, Field
from typing import Optional


# Data for creating a manual question.
class QuestionCreate(BaseModel):
    question_text: str = Field(min_length=1)
    marks: int = Field(gt=0, default=5)
    question_number: Optional[int] = Field(None, gt=0)


# Data for updating a question.
class QuestionUpdate(BaseModel):
    question_text: Optional[str] = Field(None, min_length=1)
    marks: Optional[int] = Field(None, gt=0)
