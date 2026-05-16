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
                self.client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
            self.client.ping()
            logger.info("Feature store connected OK")
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            self.client = None

    def _key(self, pid): return f"{self.KEY_PREFIX}:{pid}"

    def set(self, features, ttl=None):
        if not self.client: return False
        try:
            self.client.setex(self._key(features.product_id), ttl or settings.REDIS_TTL_SECONDS, json.dumps(features.model_dump(), default=str))
            return True
        except Exception as e:
            logger.error(f"SET failed: {e}")
            return False

    def get(self, product_id):
        if not self.client: return None
        try:
            raw = self.client.get(self._key(product_id))
            return ProductFeatures(**json.loads(raw)) if raw else None
        except Exception as e:
            logger.error(f"GET failed: {e}")
            return None

    def delete(self, product_id):
        if not self.client: return False
        return bool(self.client.delete(self._key(product_id)))

    def bulk_set(self, features_list, ttl=None):
        if not self.client:
            logger.warning("Redis not connected")
            return 0
        pipe = self.client.pipeline()
        for feat in features_list:
            pipe.setex(self._key(feat.product_id), ttl or settings.REDIS_TTL_SECONDS, json.dumps(feat.model_dump(), default=str))
        pipe.execute()
        logger.info(f"Bulk-loaded {len(features_list)} products into feature store")
        return len(features_list)

    def ttl(self, pid):
        if not self.client: return -2
        return self.client.ttl(self._key(pid))

    def stats(self):
        if not self.client: return {"status": "disconnected"}
        keys = self.client.keys(f"{self.KEY_PREFIX}:*")
        return {"status": "connected", "cached_products": len(keys)}
