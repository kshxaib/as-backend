import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # General application settings
    APP_NAME: str = os.getenv("APP_NAME", "AcademicStack")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    # PostgreSQL connection string
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Qdrant connection settings
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))


settings = Settings()