from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://library:library@localhost:5432/library"

    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    embedding_provider: str = "hash"  # "hash" | "sentence-transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    loan_period_days: int = 14
    max_active_loans: int = 5
    fine_per_day: Decimal = Decimal("0.50")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
