"""
Central configuration management for Restaurant Voice Agent.
All settings loaded from environment variables.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # ─── App ─────────────────────────────────────────────────────────────────
    APP_NAME: str = "Restaurant Voice Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: str = "*"

    # ─── JWT ─────────────────────────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ─── MongoDB ─────────────────────────────────────────────────────────────
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "restaurant_voice_agent"

    # ─── Groq ────────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_MAX_TOKENS: int = 1024
    GROQ_TEMPERATURE: float = 0.3

    # ─── Sarvam AI ───────────────────────────────────────────────────────────
    SARVAM_API_KEY: str = ""
    SARVAM_STT_MODEL: str = "saarika:v2"
    SARVAM_TTS_MODEL: str = "bulbul:v1"
    SARVAM_TTS_VOICE: str = "anushka"
    SARVAM_LANGUAGE: str = "en-IN"

    # ─── Twilio ──────────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_WEBHOOK_BASE_URL: str = ""

    # ─── ChromaDB ────────────────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION_NAME: str = "restaurant_knowledge"

    # ─── Embeddings ──────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ─── Admin ───────────────────────────────────────────────────────────────
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    ADMIN_EMAIL: str = "admin@restaurant.com"

    # ─── Restaurant ──────────────────────────────────────────────────────────
    RESTAURANT_NAME: str = "My Restaurant"
    RESTAURANT_PHONE: str = ""
    DEFAULT_TAX_PERCENTAGE: float = 5.0
    DEFAULT_DELIVERY_CHARGE: float = 30.0

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
