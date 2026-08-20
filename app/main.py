import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db.database import engine
from app.vector_store.qdrant import check_qdrant_connection


load_dotenv()


app = FastAPI(
    title=os.getenv("APP_NAME", "AcademicStack"),
    version="1.0.0",
    debug=os.getenv("DEBUG", "True").lower() == "true",
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------
# React will run on localhost:5173 during development.
#
# Without CORS, the browser will block requests from:
# React (5173) → FastAPI (8000)
#
# We configure this now so the frontend can be connected
# later without changing the backend architecture.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Basic application health
# ---------------------------------------------------------
@app.get("/api/health")
def health_check():
    """
    Check whether the FastAPI application itself is running.
    """

    return {
        "status": "ok",
        "service": os.getenv("APP_NAME", "AcademicStack"),
    }


# ---------------------------------------------------------
# PostgreSQL health
# ---------------------------------------------------------
@app.get("/api/health/db")
def database_health_check():
    """
    Check whether FastAPI can communicate with PostgreSQL.
    """

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


# ---------------------------------------------------------
# Qdrant health
# ---------------------------------------------------------
@app.get("/api/health/qdrant")
def qdrant_health_check():
    """
    Check whether FastAPI can communicate with Qdrant.
    """

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