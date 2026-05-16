"""
models/demand.py
Demand forecasting using Facebook Prophet.
Predicts unit sales over the next N days per product,
accounting for trend, seasonality, and holidays.
"""

import os
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    logger.warning("Prophet not installed. Run: pip install prophet")

from config.settings import settings


class DemandForecaster:
    """
    Per-product demand forecaster using Facebook Prophet.
    Models are trained per product and serialised as a dict of Prophet objects.

    Usage:
        forecaster = DemandForecaster()
        forecaster.train(sales_df)
        forecast = forecaster.predict("SKU-001", horizon_days=7)
    """

    def __init__(self):
        self.models: dict[str, "Prophet"] = {}
        self.product_ids: list[str] = []

    def _prepare_prophet_df(self, df: pd.DataFrame, product_id: str) -> pd.DataFrame:
        """
        Prophet requires columns: ds (datetime), y (value to forecast).
        Aggregate to daily unit sales.
        """
        prod = df[df["product_id"] == product_id].copy()
        prod["ds"] = pd.to_datetime(prod["timestamp"]).dt.floor("D")
        daily = prod.groupby("ds")["quantity"].sum().reset_index()
        daily.columns = ["ds", "y"]
        daily = daily.sort_values("ds")
        return daily

    def train(self, sales_df: pd.DataFrame, min_days: int = 30) -> dict[str, str]:
        """
        Train a Prophet model for each product.
        Products with fewer than `min_days` of history are skipped.
        Returns a dict of {product_id: status}.
        """
        if not PROPHET_AVAILABLE:
            raise RuntimeError("Install prophet: pip install prophet")

        results = {}
        all_products = sales_df["product_id"].unique()
        logger.info(f"Training demand models for {len(all_products)} products …")

        for pid in all_products:
            daily = self._prepare_prophet_df(sales_df, pid)

            if len(daily) < min_days:
                results[pid] = f"skipped (only {len(daily)} days of data)"
                continue

            try:
                model = Prophet(
                    seasonality_mode="multiplicative",
                    yearly_seasonality=True,
                    weekly_seasonality=True,
                    daily_seasonality=False,
                    changepoint_prior_scale=0.05,
                    seasonality_prior_scale=10,
                    interval_width=0.90,
                )
                model.fit(daily)
                self.models[pid] = model
                results[pid] = "trained"
            except Exception as e:
                results[pid] = f"error: {e}"
                logger.warning(f"Demand model failed for {pid}: {e}")

        trained = sum(1 for v in results.values() if v == "trained")
        logger.info(f"Demand models trained: {trained}/{len(all_products)} products")
        self.product_ids = list(self.models.keys())
        return results

    def predict(
        self,
        product_id: str,
        horizon_days: int = 7,
        include_history: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        Forecast demand for a product over the next `horizon_days` days.
        Returns a DataFrame with columns: ds, yhat, yhat_lower, yhat_upper.
        """
        if product_id not in self.models:
            logger.warning(f"No demand model for {product_id}. Using fallback.")
            return self._fallback_forecast(product_id, horizon_days)

        model = self.models[product_id]
        future = model.make_future_dataframe(periods=horizon_days, freq="D",
                                             include_history=include_history)
        forecast = model.predict(future)

        # Clip negative predictions
        forecast["yhat"]       = forecast["yhat"].clip(lower=0)
        forecast["yhat_lower"] = forecast["yhat_lower"].clip(lower=0)
        forecast["yhat_upper"] = forecast["yhat_upper"].clip(lower=0)

        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]

    def predict_next_7d_total(self, product_id: str) -> float:
        """Convenience method: return total predicted units over next 7 days."""
        fc = self.predict(product_id, horizon_days=7)
        if fc is None:
            return 0.0
        # Keep only future rows
        future = fc[fc["ds"] >= pd.Timestamp(datetime.utcnow().date())]
        return float(future["yhat"].sum())

    def _fallback_forecast(self, product_id: str, horizon_days: int) -> pd.DataFrame:
        """Return a flat forecast of 5 units/day for products without a model."""
        dates = pd.date_range(start=datetime.utcnow().date(), periods=horizon_days)
        return pd.DataFrame({
            "ds": dates,
            "yhat": [5.0] * horizon_days,
            "yhat_lower": [2.0] * horizon_days,
            "yhat_upper": [10.0] * horizon_days,
        })

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str = None):
        path = path or settings.DEMAND_MODEL_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self.models, path)
        logger.info(f"Demand models saved → {path} ({len(self.models)} products)")

    def load(self, path: str = None):
        path = path or settings.DEMAND_MODEL_PATH
        self.models = joblib.load(path)
        self.product_ids = list(self.models.keys())
        logger.info(f"Demand models loaded: {len(self.models)} products")
        return self
