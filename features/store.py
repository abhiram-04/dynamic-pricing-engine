"""
features/store.py
Redis-backed feature store for fast real-time feature retrieval.
Features are computed by the batch pipeline and cached here.
"""

import json
import redis
from datetime import datetime
from typing import Optional
from loguru import logger

from config.settings import settings
from data.schema import ProductFeatures


class FeatureStore:
    """
    Thin wrapper around Redis for storing and retrieving ProductFeatures.
    Keys are namespaced as  features:{product_id}
    """

    KEY_PREFIX = "features"

    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )
        self._check_connection()

    def _check_connection(self):
        try:
            self.client.ping()
            logger.info(f"Feature store connected: redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except redis.ConnectionError as e:
            logger.warning(f"Redis not available ({e}). Feature store running in pass-through mode.")
            self.client = None

    def _key(self, product_id: str) -> str:
        return f"{self.KEY_PREFIX}:{product_id}"

    def set(self, features: ProductFeatures, ttl: int = None) -> bool:
        """Serialise and cache a ProductFeatures object."""
        if not self.client:
            return False
        try:
            payload = features.model_dump()
            # Datetime fields aren't JSON serialisable by default
            self.client.setex(
                self._key(features.product_id),
                ttl or settings.REDIS_TTL_SECONDS,
                json.dumps(payload, default=str),
            )
            return True
        except Exception as e:
            logger.error(f"Feature store SET failed for {features.product_id}: {e}")
            return False

    def get(self, product_id: str) -> Optional[ProductFeatures]:
        """Retrieve cached features, or None if expired / missing."""
        if not self.client:
            return None
        try:
            raw = self.client.get(self._key(product_id))
            if not raw:
                return None
            return ProductFeatures(**json.loads(raw))
        except Exception as e:
            logger.error(f"Feature store GET failed for {product_id}: {e}")
            return None

    def delete(self, product_id: str) -> bool:
        """Evict cached features (e.g. after an inventory update)."""
        if not self.client:
            return False
        return bool(self.client.delete(self._key(product_id)))

    def bulk_set(self, features_list: list[ProductFeatures], ttl: int = None) -> int:
        """Batch-load features for all products (called by nightly pipeline)."""
        if not self.client:
            return 0
        pipe = self.client.pipeline()
        for feat in features_list:
            pipe.setex(
                self._key(feat.product_id),
                ttl or settings.REDIS_TTL_SECONDS,
                json.dumps(feat.model_dump(), default=str),
            )
        pipe.execute()
        logger.info(f"Bulk-loaded {len(features_list)} products into feature store")
        return len(features_list)

    def ttl(self, product_id: str) -> int:
        """Return seconds until expiry, or -2 if key does not exist."""
        if not self.client:
            return -2
        return self.client.ttl(self._key(product_id))

    def stats(self) -> dict:
        """Return basic store stats for the monitoring dashboard."""
        if not self.client:
            return {"status": "disconnected"}
        keys = self.client.keys(f"{self.KEY_PREFIX}:*")
        return {
            "status": "connected",
            "cached_products": len(keys),
            "redis_host": settings.REDIS_HOST,
            "redis_port": settings.REDIS_PORT,
        }
