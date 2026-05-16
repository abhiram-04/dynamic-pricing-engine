"""
features/pipeline.py
Transforms raw data into ML-ready feature vectors.
Runs in two modes:
  - Batch: scheduled nightly by Airflow
  - Real-time: called per pricing request
"""

import pandas as pd
import numpy as np
from datetime import datetime
from loguru import logger

from data.schema import ProductFeatures


class FeaturePipeline:
    """
    Builds ProductFeatures for one or many products from raw DataFrames.

    Usage:
        pipeline = FeaturePipeline(sales_df, inventory_df, competitor_df)
        features = pipeline.build_features("SKU-001")
    """

    def __init__(
        self,
        sales_df: pd.DataFrame,
        inventory_df: pd.DataFrame,
        competitor_df: pd.DataFrame,
    ):
        self.sales = sales_df.copy()
        self.inventory = inventory_df.copy()
        self.competitors = competitor_df.copy()
        self._preprocess()

    def _preprocess(self):
        """Normalise timestamps and ensure required columns exist."""
        self.sales["timestamp"] = pd.to_datetime(self.sales["timestamp"])
        self.sales["revenue"] = (
            self.sales["price"]
            * self.sales["quantity"]
            * (1 - self.sales.get("discount_pct", 0))
        )
        logger.debug(f"Pipeline initialised: {len(self.sales)} sales records, "
                     f"{len(self.inventory)} inventory rows, "
                     f"{len(self.competitors)} competitor prices")

    def build_features(self, product_id: str, now: datetime = None) -> ProductFeatures:
        """Return a fully populated ProductFeatures object for one product."""
        now = now or datetime.utcnow()
        cutoff_7d = now - pd.Timedelta(days=7)
        cutoff_30d = now - pd.Timedelta(days=30)

        # ── Base price (median of last 30-day sales) ──────────────────────────
        recent = self.sales[
            (self.sales["product_id"] == product_id)
            & (self.sales["timestamp"] >= cutoff_30d)
        ]
        base_price = float(recent["price"].median()) if len(recent) > 0 else 0.0
        category = recent["category"].mode()[0] if len(recent) > 0 else "unknown"

        # ── 7-day demand signals ──────────────────────────────────────────────
        week = recent[recent["timestamp"] >= cutoff_7d]
        purchases_7d = int(week["quantity"].sum())
        views_7d = purchases_7d * int(np.random.uniform(8, 20))    # stub: use real event log
        add_to_cart_7d = int(purchases_7d * np.random.uniform(2, 4))
        conversion_rate = purchases_7d / max(views_7d, 1)

        # ── Inventory signals ─────────────────────────────────────────────────
        inv = self.inventory[self.inventory["product_id"] == product_id]
        stock = int(inv["stock_quantity"].values[0]) if len(inv) > 0 else 0
        dos = float(inv["days_of_supply"].values[0]) if len(inv) > 0 else 30.0
        reorder_pt = int(inv["reorder_point"].values[0]) if len(inv) > 0 else 20
        inventory_urgency = max(0.0, min(1.0, 1.0 - (stock / max(reorder_pt * 3, 1))))

        # ── Competitor signals ────────────────────────────────────────────────
        comp = self.competitors[self.competitors["product_id"] == product_id]
        comp_avg = float(comp["competitor_price"].mean()) if len(comp) > 0 else None
        price_vs_comp = (base_price / comp_avg) if comp_avg else None

        # ── Temporal signals ──────────────────────────────────────────────────
        hour = now.hour
        dow = now.weekday()          # 0=Monday … 6=Sunday
        is_weekend = dow >= 5
        # Days until nearest payday (assume 1st and 15th of month)
        dom = now.day
        next_pay = 15 if dom < 15 else (32 - dom)   # rough approximation
        days_to_payday = min(dom - 1, next_pay) if dom <= 15 else next_pay

        return ProductFeatures(
            product_id=product_id,
            base_price=round(base_price, 2),
            category=category,
            views_7d=views_7d,
            add_to_cart_7d=add_to_cart_7d,
            purchases_7d=purchases_7d,
            conversion_rate_7d=round(conversion_rate, 4),
            stock_quantity=stock,
            days_of_supply=round(dos, 1),
            inventory_urgency=round(inventory_urgency, 3),
            competitor_avg_price=round(comp_avg, 2) if comp_avg else None,
            price_vs_competitor=round(price_vs_comp, 3) if price_vs_comp else None,
            hour_of_day=hour,
            day_of_week=dow,
            is_weekend=is_weekend,
            days_to_payday=days_to_payday,
        )

    def build_training_dataframe(self) -> pd.DataFrame:
        """
        Build a flattened feature table for all products and sales events.
        Used by scripts/train.py to create the training dataset.
        """
        rows = []
        all_products = self.sales["product_id"].unique()
        logger.info(f"Building training features for {len(all_products)} products …")

        for pid in all_products:
            prod_sales = self.sales[self.sales["product_id"] == pid].sort_values("timestamp")
            for _, row in prod_sales.iterrows():
                # Use only sales BEFORE this event (avoid future leakage)
                historical = self.sales[
                    (self.sales["product_id"] == pid)
                    & (self.sales["timestamp"] < row["timestamp"])
                ]
                if len(historical) < 5:
                    continue   # skip cold-start records

                cutoff_7d = row["timestamp"] - pd.Timedelta(days=7)
                week = historical[historical["timestamp"] >= cutoff_7d]
                purchases_7d = int(week["quantity"].sum())

                inv_row = self.inventory[self.inventory["product_id"] == pid]
                stock = int(inv_row["stock_quantity"].values[0]) if len(inv_row) > 0 else 0

                comp = self.competitors[self.competitors["product_id"] == pid]
                comp_avg = float(comp["competitor_price"].mean()) if len(comp) > 0 else None

                ts = row["timestamp"]
                rows.append({
                    "product_id":         pid,
                    "price":              row["price"],
                    "quantity":           row["quantity"],
                    "revenue":            row["revenue"],
                    "category":           row["category"],
                    "purchases_7d":       purchases_7d,
                    "stock_quantity":     stock,
                    "competitor_avg_price": comp_avg,
                    "price_vs_competitor":  (row["price"] / comp_avg) if comp_avg else None,
                    "hour_of_day":        ts.hour,
                    "day_of_week":        ts.weekday(),
                    "is_weekend":         int(ts.weekday() >= 5),
                    "user_segment":       row.get("user_segment", "standard"),
                })

        df = pd.DataFrame(rows).dropna(subset=["price", "quantity"])
        logger.info(f"Training dataframe: {len(df)} rows, {df['product_id'].nunique()} products")
        return df
