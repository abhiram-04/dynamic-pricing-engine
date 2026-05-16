"""
api/routes.py
FastAPI route handlers for the pricing service.
"""

import time
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
from loguru import logger

from data.schema import (
    PricingRequest, PricingResponse,
    BatchPricingRequest, BatchPricingResponse,
)
from config.settings import settings

router = APIRouter()


def _get_app_state(request):
    """Helper to access app state from any route."""
    return request.app.state


# ── Authentication ────────────────────────────────────────────────────────────

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if settings.API_KEY and x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """Liveness probe."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/ready")
async def readiness_check():
    """Readiness probe — ensures models are loaded."""
    return {
        "status": "ready",
        "models_loaded": True,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/price", response_model=PricingResponse)
async def get_price(
    request_body: PricingRequest,
    _: None = Depends(verify_api_key),
):
    """
    Get the AI-recommended price for a single product.

    The engine:
      1. Fetches / builds product features.
      2. Estimates price elasticity via the XGBoost model.
      3. Forecasts 7-day demand via Prophet.
      4. Optimises price to maximise expected revenue.
      5. Applies guardrails (floor, ceiling, max change).
    """
    from features.pipeline import FeaturePipeline
    from features.store import FeatureStore
    from models.optimizer import PriceOptimizer

    try:
        feature_store = FeatureStore()
        features = feature_store.get(request_body.product_id)

        if features is None:
            from data.real_ingestion import generate_real_sales_data, generate_real_inventory_data, generate_real_competitor_data
            from data.catalogue import PRODUCT_MAP
            if request_body.product_id not in PRODUCT_MAP:
                raise HTTPException(status_code=404, detail=f"Product {request_body.product_id} not found.")
            sales_df = generate_real_sales_data(days_back=30)
            inventory_df = generate_real_inventory_data()
            competitor_df = generate_real_competitor_data()
            pipeline = FeaturePipeline(sales_df, inventory_df, competitor_df)
            features = pipeline.build_features(request_body.product_id)
            product = PRODUCT_MAP[request_body.product_id]
            features.base_price = product.base_price
            features.category = product.category

        # Override inventory if caller provided it
        if request_body.inventory is not None:
            features.stock_quantity = request_body.inventory

        # Lazy-import to avoid circular deps
        from api.main import elasticity_model, demand_forecaster, guardrails
        optimizer = PriceOptimizer(elasticity_model, demand_forecaster, guardrails)
        response = optimizer.optimise(features)

        logger.info(
            f"Priced {request_body.product_id}: "
            f"{response.base_price:.2f} → {response.recommended_price:.2f} "
            f"({response.price_change_pct:+.1f}%)"
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pricing error for {request_body.product_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/price/batch", response_model=BatchPricingResponse)
async def get_batch_prices(
    request_body: BatchPricingRequest,
    _: None = Depends(verify_api_key),
):
    """Batch price multiple products in a single call."""
    start = time.perf_counter()
    results = []

    for req in request_body.requests:
        try:
            resp = await get_price(req)
            results.append(resp)
        except HTTPException as e:
            # Include a fallback for failed products so batch doesn't abort
            results.append(PricingResponse(
                product_id=req.product_id,
                recommended_price=0.0,
                base_price=0.0,
                price_change_pct=0.0,
                confidence=0.0,
                reason=f"Error: {e.detail}",
            ))

    elapsed_ms = (time.perf_counter() - start) * 1000
    return BatchPricingResponse(
        results=results,
        total_products=len(results),
        processing_time_ms=round(elapsed_ms, 1),
    )


@router.get("/products/{product_id}/features")
async def get_product_features(product_id: str):
    """Return the current feature vector for a product (for debugging)."""
    from features.store import FeatureStore
    store = FeatureStore()
    features = store.get(product_id)
    if not features:
        raise HTTPException(status_code=404, detail=f"Features not found for {product_id}")
    return features


@router.get("/products/{product_id}/forecast")
async def get_demand_forecast(product_id: str, horizon_days: int = 7):
    """Return demand forecast for a product."""
    from api.main import demand_forecaster
    forecast = demand_forecaster.predict(product_id, horizon_days=horizon_days)
    if forecast is None:
        raise HTTPException(status_code=404, detail=f"No forecast model for {product_id}")
    return forecast.to_dict(orient="records")
