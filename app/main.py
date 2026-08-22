import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db.database import engine
from app.db.init_db import init_db
from app.vector_store.qdrant import check_qdrant_connection, ensure_collection

load_dotenv()

# Initialize DB schema and run any migrations
try:
    init_db()
except Exception as e:
    print(f"Warning: init_db encountered an issue: {e}")

try:
    ensure_collection()
except Exception:
    pass

from app.users.routes import router as users_router
from app.resources.routes import router as resources_router
from app.indexing.routes import router as indexing_router
from app.question_banks.routes import router as question_banks_router
from app.questions.routes import router as questions_router
from app.answers.routes import router as answers_router
from app.community.routes import router as community_router

app = FastAPI(
    title=os.getenv("APP_NAME", "AcademicStack"),
    version="1.0.0",
    debug=os.getenv("DEBUG", "True").lower() == "true",
)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]
if os.getenv("FRONTEND_URL"):
    origins.append(os.getenv("FRONTEND_URL"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)
app.include_router(resources_router)
app.include_router(indexing_router)
app.include_router(question_banks_router)
app.include_router(questions_router)
app.include_router(answers_router)
app.include_router(community_router)


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