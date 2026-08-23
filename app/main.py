import os
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db.database import engine
from app.db.init_db import init_db
from app.vector_store.qdrant import check_qdrant_connection

load_dotenv()

IST = ZoneInfo("Asia/Kolkata")


try:
    init_db()
except Exception as e:
    print(f"Warning: init_db encountered an issue: {e}")


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

frontend_url_env = os.getenv("FRONTEND_URL", "")

if frontend_url_env:
    for url in frontend_url_env.split(","):
        clean_url = url.strip().rstrip("/")

        if clean_url and clean_url not in origins:
            origins.append(clean_url)


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


_health_lock = threading.Lock()

health_tracker = {
    "hit_count": 0,
    "last_hit_at": None,
    "server_start_time": datetime.now(IST).strftime(
        "%Y-%m-%d %I:%M:%S %p"
    ),
}


# Application Health
# Supports GET and HEAD for UptimeRobot/Render health checks

@app.api_route("/api/health", methods=["GET", "HEAD"])
def health_check():
    with _health_lock:
        health_tracker["hit_count"] += 1

        health_tracker["last_hit_at"] = datetime.now(IST).strftime(
            "%Y-%m-%d %I:%M:%S %p"
        )

    return {
        "status": "ok",
        "service": os.getenv("APP_NAME", "AcademicStack"),
        "hit_count": health_tracker["hit_count"],
        "last_hit_at": health_tracker["last_hit_at"],
        "server_start_time": health_tracker["server_start_time"],
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