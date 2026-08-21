from app.db.database import Base, engine
from app.db.models import User, Resource, QuestionBank, Question, AnswerSet, Answer

def init_db():
    Base.metadata.create_all(bind=engine)