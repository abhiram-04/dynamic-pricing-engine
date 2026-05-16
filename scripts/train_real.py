"""
scripts/train_real.py
Training pipeline using the REAL ShopSmart India product catalogue.
Replaces synthetic SKUs with actual products.

Usage:
    python scripts/train_real.py
    python scripts/train_real.py --days 365 --scrape
"""

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from loguru import logger

from data.catalogue import ALL_PRODUCTS
from data.real_ingestion import (
    generate_real_sales_data,
    generate_real_inventory_data,
    generate_real_competitor_data,
)
from features.pipeline import FeaturePipeline
from features.store import FeatureStore
from models.elasticity import ElasticityModel
from models.demand import DemandForecaster
from config.settings import settings


def train_real(days_back: int = 180, scrape_competitors: bool = False):
    logger.info("=" * 60)
    logger.info("ShopSmart India — Real Catalogue Training Pipeline")
    logger.info("=" * 60)
    logger.info(f"Products in catalogue: {len(ALL_PRODUCTS)}")
    for p in ALL_PRODUCTS:
        logger.info(f"  {p.id}  {p.name[:45]:<45}  Rs{p.base_price:>8,.0f}  {p.category}")

    logger.info(f"\nGenerating {days_back} days of sales data for real products...")
    sales_df = generate_real_sales_data(days_back=days_back)
    inventory_df = generate_real_inventory_data()

    if scrape_competitors:
        logger.info("\nScraping live competitor prices...")
        from data.scraper import CompetitorScraper
        scraper = CompetitorScraper()
        raw = scraper.scrape_all()
        competitor_df = pd.DataFrame(raw) if raw else generate_real_competitor_data()
    else:
        logger.info("\nUsing simulated competitor prices (use --scrape for live data)...")
        competitor_df = generate_real_competitor_data()

    logger.info(f"Sales records:         {len(sales_df):,}")
    logger.info(f"Products with data:    {sales_df['product_id'].nunique()}")
    logger.info(f"Revenue (simulated):   Rs{sales_df['revenue'].sum():,.0f}")

    logger.info("\nRevenue by category:")
    by_cat = sales_df.groupby("category")["revenue"].sum().sort_values(ascending=False)
    for cat, rev in by_cat.items():
        logger.info(f"  {cat:<20} Rs{rev:>12,.0f}")

    logger.info("\nBuilding feature vectors...")
    pipeline = FeaturePipeline(sales_df, inventory_df, competitor_df)
    training_df = pipeline.build_training_dataframe()
    logger.info(f"Training rows: {len(training_df):,}")

    logger.info("\nTraining XGBoost elasticity model...")
    elasticity_model = ElasticityModel()
    metrics = elasticity_model.train(training_df)
    logger.info(f"Elasticity metrics: {metrics}")
    elasticity_model.save()

    logger.info("\nTraining Prophet demand forecasters...")
    demand_forecaster = DemandForecaster()
    results = demand_forecaster.train(sales_df)
    trained = sum(1 for v in results.values() if v == "trained")
    logger.info(f"Demand models: {trained}/{len(results)} products trained")
    demand_forecaster.save()

    logger.info("\nPopulating Redis feature store with real product features...")
    store = FeatureStore()
    features_list = []
    for product in ALL_PRODUCTS:
        try:
            feat = pipeline.build_features(product.id)
            feat.base_price = product.base_price
            feat.category = product.category
            features_list.append(feat)
        except Exception as e:
            logger.warning(f"Feature build failed for {product.id}: {e}")

    n_cached = store.bulk_set(features_list)
    logger.info(f"Cached {n_cached} real products in Redis")

    logger.info("\nSample AI price recommendations:")
    logger.info(f"{'Product':<45} {'Base':>10} {'AI Rec':>10} {'Change':>8}")
    logger.info("-" * 75)

    from models.optimizer import PriceOptimizer
    from api.guardrails import PriceGuardrails
    optimizer = PriceOptimizer(elasticity_model, demand_forecaster, PriceGuardrails())

    for product in ALL_PRODUCTS:
        feat = pipeline.build_features(product.id)
        feat.base_price = product.base_price
        try:
            resp = optimizer.optimise(feat)
            chg = f"{resp.price_change_pct:+.1f}%"
            logger.info(
                f"{product.name[:44]:<45} "
                f"Rs{product.base_price:>8,.0f} "
                f"Rs{resp.recommended_price:>8,.0f} "
                f"{chg:>8}"
            )
        except Exception as e:
            logger.warning(f"Could not price {product.id}: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("Real catalogue training complete!")
    logger.info(f"  Products loaded:  {len(ALL_PRODUCTS)}")
    logger.info(f"  Feature store:    {store.stats()}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--scrape", action="store_true")
    args = parser.parse_args()
    train_real(days_back=args.days, scrape_competitors=args.scrape)
