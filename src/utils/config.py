"""
Application configuration and environment settings.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_HTML_DIR: Path = DATA_DIR / "raw_html"
    MARKDOWN_DIR: Path = DATA_DIR / "markdown"
    QDRANT_STORAGE_DIR: Path = DATA_DIR / "qdrant"
    SQLITE_DB_PATH: Path = DATA_DIR / "placidway.db"
    STATIC_DIR: Path = BASE_DIR / "static"
    DEBUG_DIR: Path = BASE_DIR / ".debug"
    

    # API Keys & Endpoints
    GEMINI_API_KEY: str = ""
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Database: Turso (Cloud) or SQLite (Local)
    TURSO_DATABASE_URL: str = ""
    TURSO_AUTH_TOKEN: str = ""

    # Qdrant Vector DB Settings
    QDRANT_MODE: str = "embedded"
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""

    # Web & Ingestion
    CRAWLER_USER_AGENT: str = "PlacidWayAssessmentBot/1.0"
    CRAWLER_RATE_LIMIT_DELAY: float = 1.0
    ROBOTS_TXT_URL: str = "https://www.placidway.com/robots.txt"

    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    MODE: str = "DEV"

    # Orchestration Settings
    DEFAULT_ORCHESTRATION_PATTERN: str = "pydantic_ai"
    EMBEDDING_MODEL_NAME: str = "gemini-embedding-001"
    PRIMARY_LLM_MODEL: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    FALLBACK_LLM_MODEL: str = "gemini-3.1-flash-lite"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_google_api_key(self) -> str:
        return self.GEMINI_API_KEY


settings = Settings()
