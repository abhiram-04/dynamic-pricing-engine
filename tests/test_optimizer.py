"""
tests/test_optimizer.py
Tests for the price optimizer and guardrails.
"""

import pytest
from unittest.mock import MagicMock, patch

from api.guardrails import PriceGuardrails
from data.schema import ProductFeatures


class TestGuardrails:

    def setup_method(self):
        self.guardrails = PriceGuardrails(
            floor_pct=0.70,
            ceiling_pct=2.00,
            max_change_pct=0.30,
            psychological_pricing=True,
        )

    def test_floor_applied(self):
        price, applied, reason = self.guardrails.apply(
            recommended=10.0, base_price=20.0
        )
        assert applied
        assert price >= 20.0 * 0.70
        assert "floor" in reason.lower()

    def test_ceiling_applied(self):
        price, applied, reason = self.guardrails.apply(
            recommended=100.0, base_price=30.0
        )
        assert applied
        assert price <= 30.0 * 2.00
        assert "ceiling" in reason.lower()

    def test_max_change_applied(self):
        price, applied, reason = self.guardrails.apply(
            recommended=50.0, base_price=30.0   # +67% change
        )
        assert applied
        assert price <= 30.0 * 1.30
        assert "change" in reason.lower()

    def test_no_guardrail_needed(self):
        price, applied, reason = self.guardrails.apply(
            recommended=31.0, base_price=30.0   # +3.3%, within all limits
        )
        assert not applied

    def test_psychological_pricing_99_ending(self):
        price, _, _ = self.guardrails.apply(
            recommended=29.85, base_price=29.0
        )
        assert str(price).endswith(".99") or str(price).endswith(".49"), \
            f"Expected .99 or .49 ending, got {price}"

    def test_price_always_positive(self):
        price, _, _ = self.guardrails.apply(recommended=0.01, base_price=50.0)
        assert price > 0

    def test_floor_less_than_ceiling(self):
        assert self.guardrails.floor_pct < self.guardrails.ceiling_pct


class TestOptimizer:

    def _make_features(self, product_id="SKU-001", base_price=30.0):
        return ProductFeatures(
            product_id=product_id,
            base_price=base_price,
            category="electronics",
            purchases_7d=15,
            stock_quantity=80,
            days_of_supply=20.0,
            inventory_urgency=0.2,
            competitor_avg_price=32.0,
            price_vs_competitor=0.94,
            hour_of_day=14,
            day_of_week=2,
            is_weekend=False,
            days_to_payday=5,
        )

    def test_optimise_returns_valid_price(self):
        from models.optimizer import PriceOptimizer

        mock_elasticity = MagicMock()
        mock_elasticity.estimate_elasticity.return_value = -1.5
        mock_elasticity.predict_quantity.return_value = 10.0

        mock_demand = MagicMock()
        mock_demand.predict_next_7d_total.return_value = 70.0

        optimizer = PriceOptimizer(mock_elasticity, mock_demand)
        features = self._make_features()
        response = optimizer.optimise(features)

        assert response.recommended_price > 0
        assert response.confidence >= 0
        assert response.confidence <= 1
        assert response.product_id == "SKU-001"

    def test_optimise_respects_base_price_floor(self):
        from models.optimizer import PriceOptimizer

        mock_elasticity = MagicMock()
        mock_elasticity.estimate_elasticity.return_value = -5.0   # extreme elasticity

        mock_demand = MagicMock()
        mock_demand.predict_next_7d_total.return_value = 1.0

        optimizer = PriceOptimizer(mock_elasticity, mock_demand,
                                   PriceGuardrails(floor_pct=0.70))
        features = self._make_features(base_price=30.0)
        response = optimizer.optimise(features)

        assert response.recommended_price >= 30.0 * 0.70, \
            f"Price {response.recommended_price} below floor {30.0 * 0.70}"

    def test_fallback_on_zero_base_price(self):
        from models.optimizer import PriceOptimizer

        optimizer = PriceOptimizer(MagicMock(), MagicMock())
        features = self._make_features(base_price=0.0)
        response = optimizer.optimise(features)

        assert response.confidence == 0.0
        assert "No base price" in response.reason
