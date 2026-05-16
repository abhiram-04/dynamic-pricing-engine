"""
tests/test_elasticity.py
Unit tests for the price elasticity model.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from models.elasticity import ElasticityModel
from data.ingestion import generate_sales_data


@pytest.fixture(scope="module")
def trained_model():
    """Train a model once for all tests in this module."""
    sales_df = generate_sales_data(n_products=10, n_records=2000, days_back=90)
    model = ElasticityModel()

    # Build minimal training df
    sales_df["revenue"] = sales_df["price"] * sales_df["quantity"]
    sales_df["price_vs_competitor"] = 1.0
    sales_df["stock_quantity"] = 50

    model.prepare_features(sales_df)
    training_df = sales_df.copy()
    training_df["log_price"] = np.log1p(training_df["price"])
    training_df["log_quantity"] = np.log1p(training_df["quantity"])
    from sklearn.preprocessing import LabelEncoder
    le = LabelEncoder()
    training_df["category_enc"] = le.fit_transform(training_df["category"])
    model.category_encoder = le

    from xgboost import XGBRegressor
    model.model = XGBRegressor(n_estimators=50, random_state=42, n_jobs=1)
    model.model.fit(
        training_df[model.feature_cols].fillna(0),
        training_df["log_quantity"],
    )
    return model


class TestElasticityModel:

    def test_predict_quantity_returns_positive(self, trained_model):
        qty = trained_model.predict_quantity(
            price=29.99,
            category="electronics",
            purchases_7d=20,
            stock_quantity=100,
        )
        assert qty >= 0, "Predicted quantity must be non-negative"

    def test_higher_price_lower_demand(self, trained_model):
        """Demand should decrease as price increases (negative elasticity)."""
        qty_low  = trained_model.predict_quantity(20.0, "electronics", 10, 50)
        qty_high = trained_model.predict_quantity(40.0, "electronics", 10, 50)
        assert qty_high <= qty_low, "Higher price should predict lower or equal demand"

    def test_elasticity_is_negative(self, trained_model):
        elasticity = trained_model.estimate_elasticity(
            price=29.99,
            category="electronics",
            purchases_7d=15,
            stock_quantity=80,
        )
        assert elasticity < 0, f"Elasticity should be negative, got {elasticity}"

    def test_elasticity_within_reasonable_range(self, trained_model):
        elasticity = trained_model.estimate_elasticity(
            price=50.0,
            category="clothing",
            purchases_7d=10,
            stock_quantity=60,
        )
        assert -10 < elasticity < 0, f"Elasticity {elasticity} out of expected range"

    def test_predict_handles_unseen_category(self, trained_model):
        """Unseen categories should not raise — should use fallback encoding."""
        qty = trained_model.predict_quantity(
            price=25.0,
            category="nonexistent_category_xyz",
            purchases_7d=5,
            stock_quantity=30,
        )
        assert qty >= 0

    def test_cold_start_elasticity_fallback(self, trained_model):
        """Zero-demand product should return the default fallback elasticity."""
        elasticity = trained_model.estimate_elasticity(
            price=100.0,
            category="electronics",
            purchases_7d=0,
            stock_quantity=0,
        )
        assert isinstance(elasticity, float)
