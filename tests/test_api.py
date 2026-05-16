"""
tests/test_api.py
Integration tests for the FastAPI endpoints.
Uses httpx's TestClient so no running server is required.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api.main import app
from data.schema import PricingResponse, ProductFeatures
from datetime import datetime


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_features():
    return ProductFeatures(
        product_id="SKU-001",
        base_price=29.99,
        category="electronics",
        purchases_7d=12,
        stock_quantity=60,
        days_of_supply=15.0,
        inventory_urgency=0.3,
        competitor_avg_price=31.50,
        price_vs_competitor=0.95,
        hour_of_day=10,
        day_of_week=1,
        is_weekend=False,
        days_to_payday=7,
    )


@pytest.fixture
def mock_pricing_response():
    return PricingResponse(
        product_id="SKU-001",
        recommended_price=32.99,
        base_price=29.99,
        price_change_pct=10.0,
        confidence=0.82,
        reason="High demand signal supports price increase",
        guardrail_applied=False,
        timestamp=datetime.utcnow(),
    )


class TestHealthEndpoints:

    def test_health_check(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_readiness_check(self, client):
        resp = client.get("/api/v1/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"


class TestPricingEndpoint:

    def test_price_returns_404_for_unknown_product(self, client):
        resp = client.post(
            "/api/v1/price",
            json={"product_id": "NONEXISTENT-999"},
        )
        assert resp.status_code == 404

    @patch("api.routes.FeatureStore")
    @patch("api.routes.PriceOptimizer")
    @patch("api.main.elasticity_model")
    @patch("api.main.demand_forecaster")
    def test_price_returns_valid_response(
        self, mock_demand, mock_elasticity,
        MockOptimizer, MockStore,
        client, mock_features, mock_pricing_response
    ):
        mock_store_instance = MagicMock()
        mock_store_instance.get.return_value = mock_features
        MockStore.return_value = mock_store_instance

        mock_optimizer_instance = MagicMock()
        mock_optimizer_instance.optimise.return_value = mock_pricing_response
        MockOptimizer.return_value = mock_optimizer_instance

        resp = client.post(
            "/api/v1/price",
            json={"product_id": "SKU-001", "user_segment": "loyal"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_id"] == "SKU-001"
        assert data["recommended_price"] > 0
        assert 0 <= data["confidence"] <= 1
        assert "reason" in data

    def test_price_request_schema_validation(self, client):
        """Missing product_id should return 422."""
        resp = client.post("/api/v1/price", json={"user_segment": "vip"})
        assert resp.status_code == 422


class TestBatchPricingEndpoint:

    @patch("api.routes.FeatureStore")
    def test_batch_returns_results_for_all_products(self, MockStore, client):
        mock_store_instance = MagicMock()
        mock_store_instance.get.return_value = None   # 404 for all
        MockStore.return_value = mock_store_instance

        resp = client.post(
            "/api/v1/price/batch",
            json={"requests": [
                {"product_id": "SKU-A"},
                {"product_id": "SKU-B"},
            ]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_products"] == 2
        assert len(data["results"]) == 2
        assert "processing_time_ms" in data
