"""
scripts/backtest.py
Simulates the pricing engine on historical data and compares
revenue vs a baseline (static pricing) strategy.

Usage:
    python scripts/backtest.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import pandas as pd
from loguru import logger

from data.ingestion import generate_sales_data, generate_inventory_data, generate_competitor_data
from features.pipeline import FeaturePipeline
from models.elasticity import ElasticityModel
from models.demand import DemandForecaster
from models.optimizer import PriceOptimizer
from api.guardrails import PriceGuardrails
from config.settings import settings


def backtest(n_products: int = 20, n_records: int = 5_000):
    logger.info("Running revenue backtest …")

    # Generate data and split train / test by time
    sales_df     = generate_sales_data(n_products=n_products, n_records=n_records, days_back=180)
    inventory_df = generate_inventory_data(n_products=n_products)
    competitor_df= generate_competitor_data(n_products=n_products)

    cutoff = sales_df["timestamp"].quantile(0.8)
    train_df = sales_df[sales_df["timestamp"] < cutoff]
    test_df  = sales_df[sales_df["timestamp"] >= cutoff]

    # Train models on training split
    pipeline = FeaturePipeline(train_df, inventory_df, competitor_df)
    training_features = pipeline.build_training_dataframe()

    elasticity_model  = ElasticityModel()
    elasticity_model.train(training_features)

    demand_forecaster = DemandForecaster()
    demand_forecaster.train(train_df)

    optimizer = PriceOptimizer(elasticity_model, demand_forecaster, PriceGuardrails())

    # Simulate pricing on test split
    baseline_revenue = 0.0
    optimised_revenue = 0.0
    n_priced = 0

    for _, row in test_df.iterrows():
        features = pipeline.build_features(row["product_id"])
        baseline_price = row["price"]   # what was actually charged
        baseline_qty   = row["quantity"]
        baseline_revenue += baseline_price * baseline_qty

        try:
            response = optimizer.optimise(features)
            opt_price = response.recommended_price
            # Simulate quantity response via estimated elasticity
            if features.base_price > 0:
                ratio     = opt_price / features.base_price
                elasticity = -1.5      # conservative assumption for simulation
                opt_qty   = max(0, baseline_qty * (ratio ** elasticity))
            else:
                opt_qty = baseline_qty
            optimised_revenue += opt_price * opt_qty
            n_priced += 1
        except Exception as e:
            optimised_revenue += baseline_price * baseline_qty   # fallback

    revenue_lift_pct = (optimised_revenue - baseline_revenue) / max(baseline_revenue, 1) * 100

    logger.info(f"\n{'='*50}")
    logger.info(f"Backtest Results ({n_priced} pricing events)")
    logger.info(f"  Baseline revenue:   ${baseline_revenue:,.2f}")
    logger.info(f"  Optimised revenue:  ${optimised_revenue:,.2f}")
    logger.info(f"  Revenue lift:       {revenue_lift_pct:+.1f}%")
    logger.info(f"{'='*50}")

    return {
        "baseline_revenue": round(baseline_revenue, 2),
        "optimised_revenue": round(optimised_revenue, 2),
        "revenue_lift_pct": round(revenue_lift_pct, 1),
        "n_priced": n_priced,
    }


if __name__ == "__main__":
    backtest()
