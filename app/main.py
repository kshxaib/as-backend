import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db.database import engine
from app.vector_store.qdrant import check_qdrant_connection

from app.users.routes import router as users_router
from app.resources.routes import router as resources_router
from app.indexing.routes import router as indexing_router
from app.question_banks.routes import router as question_banks_router
from app.questions.routes import router as questions_router



load_dotenv()


app = FastAPI(
    title=os.getenv("APP_NAME", "AcademicStack"),
    version="1.0.0",
    debug=os.getenv("DEBUG", "True").lower() == "true",
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        os.getenv("FRONTEND_URL")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(users_router)
app.include_router(resources_router)
app.include_router(indexing_router)
app.include_router(question_banks_router)
app.include_router(questions_router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": os.getenv("APP_NAME", "AcademicStack"),
    }


@app.get("/api/health/db")
def database_health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
        }

    except Exception as error:
        return {
            "status": "error",
            "database": "disconnected",
            "detail": str(error),
        }


@app.get("/api/health/qdrant")
def qdrant_health_check():
    is_connected = check_qdrant_connection()

    if is_connected:
        return {
            "status": "ok",
            "qdrant": "connected",
        }

    return {
        "status": "error",
        "qdrant": "disconnected",
    }