"""
config/settings.py
Central configuration loaded from environment variables or .env file.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://pricing_user:pricing_pass@localhost:5432/pricing_db"

    # ── Redis (feature store) ─────────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_TTL_SECONDS: int = 300          # 5-min cache for feature vectors

    # ── Kafka (streaming pipeline) ────────────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_EVENTS: str = "user_events"
    KAFKA_TOPIC_PRICES: str = "price_updates"

    # ── MLflow ────────────────────────────────────────────────────────────────
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MLFLOW_EXPERIMENT_NAME: str = "dynamic_pricing"

    # ── Pricing guardrails ────────────────────────────────────────────────────
    PRICE_FLOOR_PCT: float = 0.70         # Never below 70% of base price
    PRICE_CEILING_PCT: float = 2.00       # Never above 200% of base price
    MAX_PRICE_CHANGE_PCT: float = 0.30    # Max 30% change per pricing event

    # ── Model paths ───────────────────────────────────────────────────────────
    MODEL_DIR: str = "models/saved"
    ELASTICITY_MODEL_PATH: str = "models/saved/elasticity_model.pkl"
    DEMAND_MODEL_PATH: str = "models/saved/demand_model.pkl"

    # ── Competitor scraping ───────────────────────────────────────────────────
    COMPETITOR_SCRAPE_INTERVAL_MINS: int = 60
    COMPETITOR_URLS: list[str] = []

    # ── API ───────────────────────────────────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    API_KEY: Optional[str] = None         # If set, require X-API-Key header

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
