"""
scripts/train.py
End-to-end training script.
Generates synthetic data (or loads from CSV), builds features,
trains elasticity + demand models, and saves artifacts.

Usage:
    python scripts/train.py
    python scripts/train.py --data data/sales.csv --products 100
"""

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from loguru import logger

from data.ingestion import generate_sales_data, generate_inventory_data, generate_competitor_data
from features.pipeline import FeaturePipeline
from features.store import FeatureStore
from models.elasticity import ElasticityModel
from models.demand import DemandForecaster
from config.settings import settings


def train(
    data_path: str = None,
    n_products: int = 50,
    n_records: int = 10_000,
):
    logger.info("=" * 60)
    logger.info("Dynamic Pricing Engine — Training Pipeline")
    logger.info("=" * 60)

    # ── 1. Load or generate data ──────────────────────────────────────────────
    if data_path and os.path.exists(data_path):
        logger.info(f"Loading sales data from {data_path}")
        sales_df = pd.read_csv(data_path, parse_dates=["timestamp"])
    else:
        logger.info(f"Generating synthetic data ({n_products} products, {n_records:,} records)")
        sales_df = generate_sales_data(n_products=n_products, n_records=n_records)

    inventory_df   = generate_inventory_data(n_products=n_products)
    competitor_df  = generate_competitor_data(n_products=n_products)

    logger.info(f"Sales records:      {len(sales_df):,}")
    logger.info(f"Inventory rows:     {len(inventory_df)}")
    logger.info(f"Competitor entries: {len(competitor_df)}")

    # ── 2. Build training features ────────────────────────────────────────────
    logger.info("\nBuilding feature vectors …")
    pipeline = FeaturePipeline(sales_df, inventory_df, competitor_df)
    training_df = pipeline.build_training_dataframe()
    logger.info(f"Training rows: {len(training_df):,}")

    # ── 3. Train elasticity model ─────────────────────────────────────────────
    logger.info("\nTraining elasticity model (XGBoost) …")
    elasticity_model = ElasticityModel()
    metrics = elasticity_model.train(training_df)
    logger.info(f"Elasticity model metrics: {metrics}")
    elasticity_model.save()

    # ── 4. Train demand forecasters ───────────────────────────────────────────
    logger.info("\nTraining demand forecasting models (Prophet) …")
    demand_forecaster = DemandForecaster()
    results = demand_forecaster.train(sales_df)
    trained = sum(1 for v in results.values() if v == "trained")
    logger.info(f"Demand models: {trained}/{len(results)} trained successfully")
    demand_forecaster.save()

    # ── 5. Populate feature store ─────────────────────────────────────────────
    logger.info("\nPopulating feature store (Redis) …")
    store = FeatureStore()
    all_products = sales_df["product_id"].unique()
    features_list = []
    for pid in all_products:
        try:
            feat = pipeline.build_features(pid)
            features_list.append(feat)
        except Exception as e:
            logger.warning(f"Feature build failed for {pid}: {e}")

    n_cached = store.bulk_set(features_list)
    logger.info(f"Cached {n_cached} product feature vectors in Redis")

    # ── 6. Summary ────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("Training complete!")
    logger.info(f"  Elasticity model → {settings.ELASTICITY_MODEL_PATH}")
    logger.info(f"  Demand models    → {settings.DEMAND_MODEL_PATH}")
    logger.info(f"  Feature store    → {store.stats()}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the dynamic pricing engine")
    parser.add_argument("--data", type=str, default=None,
                        help="Path to a CSV with historical sales data")
    parser.add_argument("--products", type=int, default=50,
                        help="Number of synthetic products to generate")
    parser.add_argument("--records", type=int, default=10_000,
                        help="Number of synthetic sales records to generate")
    args = parser.parse_args()

    train(data_path=args.data, n_products=args.products, n_records=args.records)
