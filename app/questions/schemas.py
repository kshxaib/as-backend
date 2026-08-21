from pydantic import BaseModel, Field
from typing import Optional


# Data for updating a question.
class QuestionUpdate(BaseModel):
    question_text: Optional[str] = Field(None, min_length=1)
    marks: Optional[int] = Field(None, gt=0)
