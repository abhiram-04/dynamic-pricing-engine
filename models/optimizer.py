"""
models/optimizer.py
Price optimizer — given demand predictions and price elasticity,
finds the price that maximises expected revenue subject to business constraints.

Uses scipy.optimize.minimize_scalar for fast 1D optimisation.
"""

import numpy as np
from scipy.optimize import minimize_scalar
from loguru import logger

from data.schema import ProductFeatures, PricingResponse
from models.elasticity import ElasticityModel
from models.demand import DemandForecaster
from api.guardrails import PriceGuardrails


class PriceOptimizer:
    """
    Core optimisation engine.

    For each pricing request:
      1. Estimate price elasticity at current price.
      2. Compute demand curve: Q(P) = Q_base * (P/P_base)^ε
      3. Optimise P to maximise Revenue = P * Q(P)
      4. Apply guardrails (floor, ceiling, max change).
    """

    def __init__(
        self,
        elasticity_model: ElasticityModel,
        demand_forecaster: DemandForecaster,
        guardrails: PriceGuardrails = None,
    ):
        self.elasticity_model = elasticity_model
        self.demand_forecaster = demand_forecaster
        self.guardrails = guardrails or PriceGuardrails()

    def optimise(self, features: ProductFeatures) -> PricingResponse:
        """
        Main entry point: return an optimised PricingResponse.
        """
        base_price = features.base_price
        if base_price <= 0:
            return self._fallback_response(features, "No base price available")

        # ── Step 1: Estimate elasticity at current price ──────────────────────
        elasticity = self.elasticity_model.estimate_elasticity(
            price=base_price,
            category=features.category,
            purchases_7d=features.purchases_7d,
            stock_quantity=features.stock_quantity,
            price_vs_competitor=features.price_vs_competitor or 1.0,
            hour_of_day=features.hour_of_day,
            day_of_week=features.day_of_week,
            is_weekend=features.is_weekend,
        )

        # ── Step 2: Estimate base demand ──────────────────────────────────────
        q_base = self.demand_forecaster.predict_next_7d_total(features.product_id)
        if q_base <= 0:
            q_base = max(features.purchases_7d, 1)

        # ── Step 3: Define revenue objective ─────────────────────────────────
        # Demand model: Q(P) = Q_base * (P / P_base)^ε
        # Revenue:      R(P) = P * Q(P)
        def neg_revenue(price):
            demand = q_base * ((price / base_price) ** elasticity)
            return -(price * max(demand, 0))

        # Search over [floor_price, ceiling_price]
        floor_price   = base_price * self.guardrails.floor_pct
        ceiling_price = base_price * self.guardrails.ceiling_pct

        result = minimize_scalar(
            neg_revenue,
            bounds=(floor_price, ceiling_price),
            method="bounded",
        )

        optimal_price = result.x

        # ── Step 4: Apply contextual adjustments ──────────────────────────────
        optimal_price = self._apply_context_adjustments(optimal_price, features, base_price)

        # ── Step 5: Apply guardrails ──────────────────────────────────────────
        final_price, guardrail_applied, guardrail_reason = self.guardrails.apply(
            recommended=optimal_price,
            base_price=base_price,
        )
        final_price = round(final_price, 2)

        # ── Step 6: Build response ────────────────────────────────────────────
        price_change_pct = (final_price - base_price) / base_price * 100
        confidence = self._compute_confidence(features, elasticity)

        reason = guardrail_reason if guardrail_applied else self._explain(
            features, price_change_pct, elasticity
        )

        return PricingResponse(
            product_id=features.product_id,
            recommended_price=final_price,
            base_price=base_price,
            price_change_pct=round(price_change_pct, 1),
            confidence=round(confidence, 2),
            reason=reason,
            guardrail_applied=guardrail_applied,
        )

    def _apply_context_adjustments(
        self, price: float, features: ProductFeatures, base_price: float
    ) -> float:
        """
        Layer on heuristic adjustments not captured by the pure revenue model.
        """
        adjusted = price

        # Inventory pressure: if near stockout, push price up to protect margin
        if features.inventory_urgency > 0.85:
            adjusted *= 1.08
            logger.debug(f"{features.product_id}: inventory urgency boost +8%")

        # Competitor undercut protection: if we're 15%+ above competition, ease back
        if features.price_vs_competitor and features.price_vs_competitor > 1.15:
            adjusted = min(adjusted, features.competitor_avg_price * 1.10)
            logger.debug(f"{features.product_id}: competitor alignment applied")

        # Weekend demand premium for certain categories
        if features.is_weekend and features.category in ("beauty", "clothing"):
            adjusted *= 1.03

        return adjusted

    def _compute_confidence(self, features: ProductFeatures, elasticity: float) -> float:
        """
        Heuristic confidence score [0, 1].
        Higher when: sufficient demand history, elasticity in normal range, stock available.
        """
        score = 0.5

        # Demand data quality
        if features.purchases_7d >= 10:
            score += 0.20
        elif features.purchases_7d >= 3:
            score += 0.10

        # Elasticity plausibility
        if -3.0 < elasticity < -0.3:
            score += 0.20
        elif -5.0 < elasticity < 0:
            score += 0.10

        # Inventory known
        if features.stock_quantity > 0:
            score += 0.05

        # Competitor signal available
        if features.competitor_avg_price:
            score += 0.05

        return min(score, 1.0)

    def _explain(
        self, features: ProductFeatures, change_pct: float, elasticity: float
    ) -> str:
        if change_pct > 10:
            return f"High demand signal (elasticity {elasticity:.1f}) supports price increase"
        elif change_pct < -10:
            return "Weak demand; price reduction expected to recover volume"
        elif features.inventory_urgency > 0.7:
            return "Low inventory; marginal price increase to slow depletion"
        elif features.price_vs_competitor and features.price_vs_competitor > 1.10:
            return "Competitor prices lower; aligning to maintain conversion"
        else:
            return "Price near revenue-optimal point; minor adjustment"

    def _fallback_response(self, features: ProductFeatures, reason: str) -> PricingResponse:
        return PricingResponse(
            product_id=features.product_id,
            recommended_price=features.base_price,
            base_price=features.base_price,
            price_change_pct=0.0,
            confidence=0.0,
            reason=reason,
            guardrail_applied=False,
        )
