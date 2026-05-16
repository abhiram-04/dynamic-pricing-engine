"""
models/elasticity.py
Price elasticity model using XGBoost.
Estimates how demand (quantity) responds to price changes per product/category.
Outputs elasticity coefficients used by the optimizer.
"""

import os
import joblib
import numpy as np
import pandas as pd
import mlflow
import mlflow.xgboost
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_percentage_error, r2_score
from loguru import logger

from config.settings import settings


FEATURE_COLS = [
    "log_price",
    "category_enc",
    "purchases_7d",
    "stock_quantity",
    "price_vs_competitor",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
]
TARGET_COL = "log_quantity"


class ElasticityModel:
    """
    Trains and serves an XGBoost model that predicts log(quantity)
    from log(price) and contextual features.
    The elasticity at a given price is approximated as the partial
    derivative d(log Q) / d(log P), estimated via finite differences.
    """

    def __init__(self):
        self.model: XGBRegressor = None
        self.category_encoder = LabelEncoder()
        self.feature_cols = FEATURE_COLS
        self.version = "1.0.0"

    # ── Training ──────────────────────────────────────────────────────────────

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform raw training dataframe into model-ready features."""
        out = df.copy()
        out["log_price"]    = np.log1p(out["price"])
        out["log_quantity"] = np.log1p(out["quantity"])
        out["category_enc"] = self.category_encoder.fit_transform(
            out["category"].fillna("unknown")
        )
        out["price_vs_competitor"] = out["price_vs_competitor"].fillna(1.0)
        out["stock_quantity"]      = out["stock_quantity"].fillna(50)
        return out

    def train(self, df: pd.DataFrame, experiment_name: str = None) -> dict:
        """
        Train the XGBoost elasticity model.
        Logs metrics and the model artifact to MLflow.
        """
        experiment_name = experiment_name or settings.MLFLOW_EXPERIMENT_NAME
        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(experiment_name)

        prepared = self.prepare_features(df)
        X = prepared[self.feature_cols].fillna(0)
        y = prepared[TARGET_COL]

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        params = {
            "n_estimators":     400,
            "max_depth":        6,
            "learning_rate":    0.05,
            "subsample":        0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 5,
            "reg_lambda":       1.0,
            "random_state":     42,
            "n_jobs":           -1,
        }

        with mlflow.start_run(run_name="elasticity_model"):
            self.model = XGBRegressor(**params)
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_test, y_test)],
                verbose=False,
            )

            preds = self.model.predict(X_test)
            mape  = mean_absolute_percentage_error(y_test, preds)
            r2    = r2_score(y_test, preds)

            mlflow.log_params(params)
            mlflow.log_metrics({"test_mape": mape, "test_r2": r2})
            mlflow.xgboost.log_model(self.model, artifact_path="elasticity_model")

            metrics = {"test_mape": round(mape, 4), "test_r2": round(r2, 4)}
            logger.info(f"Elasticity model trained → MAPE={mape:.3f}, R²={r2:.3f}")

        return metrics

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict_quantity(
        self,
        price: float,
        category: str,
        purchases_7d: int,
        stock_quantity: int,
        price_vs_competitor: float = 1.0,
        hour_of_day: int = 12,
        day_of_week: int = 1,
        is_weekend: bool = False,
    ) -> float:
        """Predict demand quantity for a given price and context."""
        if not self.model:
            raise RuntimeError("Model not trained. Call train() or load() first.")

        # Encode category safely
        try:
            cat_enc = self.category_encoder.transform([category])[0]
        except ValueError:
            cat_enc = 0   # fallback for unseen categories

        X = pd.DataFrame([{
            "log_price":           np.log1p(price),
            "category_enc":        cat_enc,
            "purchases_7d":        purchases_7d,
            "stock_quantity":      stock_quantity,
            "price_vs_competitor": price_vs_competitor,
            "hour_of_day":         hour_of_day,
            "day_of_week":         day_of_week,
            "is_weekend":          int(is_weekend),
        }])

        log_qty = self.model.predict(X)[0]
        return float(np.expm1(log_qty))

    def estimate_elasticity(self, price: float, **kwargs) -> float:
        """
        Estimate price elasticity at a given price using finite differences:
            ε ≈ (ΔQ/Q) / (ΔP/P)
        Typically negative: ε=-1.5 means 10% price rise → 15% demand drop.
        """
        delta = price * 0.01   # 1% price perturbation
        q_high = self.predict_quantity(price + delta, **kwargs)
        q_low  = self.predict_quantity(price - delta, **kwargs)
        q_base = self.predict_quantity(price, **kwargs)

        if q_base < 1e-6:
            return -1.0   # default elasticity for cold-start

        elasticity = ((q_high - q_low) / (2 * delta)) * (price / q_base)
        return round(float(elasticity), 3)

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str = None):
        path = path or settings.ELASTICITY_MODEL_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump({"model": self.model, "encoder": self.category_encoder}, path)
        logger.info(f"Elasticity model saved → {path}")

    def load(self, path: str = None):
        path = path or settings.ELASTICITY_MODEL_PATH
        artifact = joblib.load(path)
        self.model = artifact["model"]
        self.category_encoder = artifact["encoder"]
        logger.info(f"Elasticity model loaded from {path}")
        return self
