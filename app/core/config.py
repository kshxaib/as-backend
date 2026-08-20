import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "AcademicStack")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    DATABASE_URL: str = os.getenv("DATABASE_URL")
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))


settings = Settings()