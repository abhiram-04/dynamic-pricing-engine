"""
api/main.py
FastAPI application entry point.
Loads models on startup and exposes them as module-level singletons.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config.settings import settings
from models.elasticity import ElasticityModel
from models.demand import DemandForecaster
from api.guardrails import PriceGuardrails

# ── Module-level model singletons (shared across requests) ────────────────────
elasticity_model  = ElasticityModel()
demand_forecaster = DemandForecaster()
guardrails        = PriceGuardrails()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load ML models on startup; clean up on shutdown."""
    logger.info("Starting Dynamic Pricing Engine …")

    # Load pre-trained models if they exist on disk
    if os.path.exists(settings.ELASTICITY_MODEL_PATH):
        elasticity_model.load(settings.ELASTICITY_MODEL_PATH)
    else:
        logger.warning(
            f"Elasticity model not found at {settings.ELASTICITY_MODEL_PATH}. "
            "Run: python scripts/train.py"
        )

    if os.path.exists(settings.DEMAND_MODEL_PATH):
        demand_forecaster.load(settings.DEMAND_MODEL_PATH)
    else:
        logger.warning(
            f"Demand model not found at {settings.DEMAND_MODEL_PATH}. "
            "Run: python scripts/train.py"
        )

    logger.info("Models loaded. API ready.")
    yield
    logger.info("Shutting down pricing engine.")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Dynamic Pricing Engine",
    description="AI-powered real-time price optimisation for e-commerce.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.routes import router   # noqa: E402 (import after app creation)
app.include_router(router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=settings.API_WORKERS,
        reload=True,
    )
