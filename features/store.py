import os
import json
import redis
from typing import Optional
from loguru import logger
from config.settings import settings
from data.schema import ProductFeatures

class FeatureStore:
    KEY_PREFIX = "features"

    def __init__(self):
        try:
            redis_url = os.environ.get("REDIS_URL")
            if redis_url:
                self.client = redis.Redis.from_url(redis_url, decode_responses=True)
                logger.info("Feature store connecting via REDIS_URL")
            else:
                self.client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    decode_responses=True,
                )
            self._check_connection()
        except Exception as e:
            logger.warning(f"Redis init failed: {e}")
            self.client = None

    def _check_connection(self):
        try:
            self.client.p