"""Environment configuration for EduTrack AI backend."""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    """Base configuration loaded from environment variables."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/edutrack_ai",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT — tokens delivered via httpOnly cookies (see auth routes)
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_SECURE = os.getenv("FLASK_ENV") == "production"
    JWT_COOKIE_HTTPONLY = True
    JWT_COOKIE_SAMESITE = "Strict"
    JWT_COOKIE_CSRF_PROTECT = True

    # LLM — OpenAI-compatible by default (TeamoRouter / OpenAI / DeepSeek / Groq…)
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # openai | anthropic
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
    LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
    LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-flash-free")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # ChromaDB
    CHROMA_PERSIST_DIR = os.getenv(
        "CHROMA_PERSIST_DIR",
        str(BASE_DIR / "data" / "chroma_store"),
    )
    CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "dse_knowledge_base")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

    # RAG tuning
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
    RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.65"))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
