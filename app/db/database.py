import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from dotenv import load_dotenv

load_dotenv()


# SQLAlchemy engine.
# The engine manages the connection between FastAPI and PostgreSQL.
engine = create_engine(
    os.getenv("DATABASE_URL"),
    pool_pre_ping=True,
)


# Creates database sessions.
# Each API request can use one session to interact with PostgreSQL.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# Base class for all SQLAlchemy database models.
Base = declarative_base()


def get_db():

    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()