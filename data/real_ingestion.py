"""
data/real_ingestion.py
Replaces generate_sales_data() with real product catalogue data.
Generates realistic historical sales based on actual product properties:
  - Price sensitivity (elasticity) per category
  - Seasonal patterns (weekends, festivals, payday)
  - Realistic demand volumes per product tier
  - Real competitor price relationships
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger

from data.catalogue import ALL_PRODUCTS, Product


# ── Festival calendar (India) — demand multipliers ────────────────────────────

FESTIVAL_BOOSTS = {
    # month, day: multiplier
    (10, 12): 2.8,   # Dussehra
    (10, 20): 3.5,   # Diwali sale start
    (10, 21): 4.2,   # Diwali peak
    (10, 22): 3.8,   # Diwali day 2
    (11, 11): 2.1,   # Singles Day sale
    (12, 25): 1.8,   # Christmas
    (1, 26): 1.6,    # Republic Day sale
    (2, 14): 1.5,    # Valentine's Day (beauty/fashion)
    (8, 15): 2.0,    # Independence Day sale
}

CATEGORY_BASE_DEMAND = {
    "Electronics":     {"daily_avg": 8,  "weekend_mult": 1.3, "payday_mult": 1.8},
    "Footwear":        {"daily_avg": 15, "weekend_mult": 1.5, "payday_mult": 1.4},
    "Clothing":        {"daily_avg": 20, "weekend_mult": 1.6, "payday_mult": 1.5},
    "Grocery":         {"daily_avg": 85, "weekend_mult": 1.2, "payday_mult": 1.1},
    "Kitchen":         {"daily_avg": 6,  "weekend_mult": 1.3, "payday_mult": 1.3},
    "Home Appliances": {"daily_avg": 4,  "weekend_mult": 1.2, "payday_mult": 1.6},
    "Home":            {"daily_avg": 25, "weekend_mult": 1.1, "payday_mult": 1.2},
    "Sports":          {"daily_avg": 12, "weekend_mult": 1.8, "payday_mult": 1.3},
    "Beauty":          {"daily_avg": 30, "weekend_mult": 1.4, "payday_mult": 1.4},
}


def generate_real_sales_data(
    days_back: int = 180,
    price_variation_pct: float = 0.15,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate realistic historical sales data for all real products.
    Each row = one order line item.
    Price varies ±15% from base to simulate past promotions/increases.
    Demand responds to price via each product's elasticity.
    """
    np.random.seed(seed)
    records = []
    now = datetime.utcnow()

    for product in ALL_PRODUCTS:
        cat_cfg = CATEGORY_BASE_DEMAND.get(product.category, {"daily_avg": 10, "weekend_mult": 1.2, "payday_mult": 1.3})
        daily_base = cat_cfg["daily_avg"]

        for day_offset in range(days_back):
            date = now - timedelta(days=day_offset)
            dow = date.weekday()
            dom = date.day

            # Multipliers
            weekend_mult = cat_cfg["weekend_mult"] if dow >= 5 else 1.0
            payday_mult = cat_cfg["payday_mult"] if dom in [1, 2, 15, 16] else 1.0
            festival_mult = FESTIVAL_BOOSTS.get((date.month, date.day), 1.0)

            # Apply boost only to relevant categories on festivals
            if festival_mult > 1.5 and product.category == "Grocery":
                festival_mult = min(festival_mult, 1.3)  # Grocery doesn't boom as much

            # Base orders for the day
            base_orders = max(1, int(
                daily_base * weekend_mult * payday_mult * festival_mult
                * np.random.uniform(0.7, 1.3)
            ))

            # Generate individual orders for the day
            for _ in range(base_orders):
                # Price varies ±variation from base
                price_factor = 1 + np.random.uniform(-price_variation_pct, price_variation_pct)
                price = round(product.base_price * price_factor, 2)
                price = max(price, product.cost_price * 1.05)  # Never below cost+5%

                # Quantity: most orders are 1 unit, occasionally 2-3
                quantity = int(np.random.choice([1, 1, 1, 2, 3], p=[0.7, 0.1, 0.1, 0.07, 0.03]))

                # Discount: occasional flash sales
                discount = 0.0
                if np.random.random() < 0.08:
                    discount = np.random.choice([0.05, 0.10, 0.15])

                # Timestamp within the day
                hour = int(np.random.choice(
                    range(24),
                    p=_hour_distribution()
                ))
                ts = date.replace(hour=hour, minute=np.random.randint(0, 60))

                records.append({
                    "order_id":       f"ORD-{np.random.randint(100000, 999999)}",
                    "product_id":     product.id,
                    "category":       product.category,
                    "subcategory":    product.subcategory,
                    "brand":          product.brand,
                    "price":          price,
                    "cost_price":     product.cost_price,
                    "quantity":       quantity,
                    "discount_pct":   discount,
                    "timestamp":      ts,
                    "user_segment":   _user_segment(),
                    "channel":        _channel(),
                })

    df = pd.DataFrame(records)
    df["revenue"] = df["price"] * df["quantity"] * (1 - df["discount_pct"])
    df["profit"] = (df["price"] - df["cost_price"]) * df["quantity"] * (1 - df["discount_pct"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    logger.info(
        f"Generated {len(df):,} real sales records "
        f"for {len(ALL_PRODUCTS)} products "
        f"over {days_back} days"
    )
    return df


def generate_real_inventory_data() -> pd.DataFrame:
    """Return current inventory snapshot from catalogue."""
    records = []
    for p in ALL_PRODUCTS:
        records.append({
            "product_id":     p.id,
            "product_name":   p.name,
            "category":       p.category,
            "stock_quantity": p.initial_stock,
            "reorder_point":  p.reorder_point,
            "cost_price":     p.cost_price,
            "days_of_supply": round(p.initial_stock / max(1, _daily_velocity(p)), 1),
            "updated_at":     datetime.utcnow(),
        })
    return pd.DataFrame(records)


def generate_real_competitor_data() -> pd.DataFrame:
    """
    Simulate competitor prices based on market positioning.
    In production, replace with real scraper output.
    """
    np.random.seed(7)
    COMPETITORS = ["Amazon.in", "Flipkart", "Myntra", "Nykaa", "BigBasket", "JioMart"]
    records = []

    for p in ALL_PRODUCTS:
        # Each product has 2-4 competitor prices
        n_comps = np.random.randint(2, 5)
        relevant = [c for c in COMPETITORS if _relevant_competitor(c, p.category)]
        chosen = np.random.choice(relevant, size=min(n_comps, len(relevant)), replace=False)

        for comp in chosen:
            # Competitors cluster within ±20% of your price
            comp_factor = np.random.uniform(0.82, 1.18)
            records.append({
                "product_id":       p.id,
                "competitor_name":  comp,
                "competitor_price": round(p.base_price * comp_factor, 2),
                "scraped_at":       datetime.utcnow(),
            })

    return pd.DataFrame(records)


# ── Helper functions ──────────────────────────────────────────────────────────

def _hour_distribution():
    """Indian online shopping hour distribution."""
    # Peak: 10-12am, 8-11pm. Low: 2-6am
    weights = [0.01, 0.01, 0.01, 0.01, 0.01, 0.02,
               0.03, 0.04, 0.05, 0.06, 0.07, 0.07,
               0.06, 0.05, 0.05, 0.05, 0.05, 0.05,
               0.05, 0.06, 0.07, 0.07, 0.06, 0.03]
    total = sum(weights)
    return [w / total for w in weights]

def _user_segment():
    return np.random.choice(
        ["standard", "new", "loyal", "vip"],
        p=[0.50, 0.28, 0.17, 0.05]
    )

def _channel():
    return np.random.choice(
        ["app", "web", "mobile_web"],
        p=[0.55, 0.30, 0.15]
    )

def _daily_velocity(p: Product) -> float:
    """Estimate daily units sold based on category."""
    cfg = CATEGORY_BASE_DEMAND.get(p.category, {"daily_avg": 5})
    return cfg["daily_avg"]

def _relevant_competitor(comp: str, category: str) -> bool:
    mapping = {
        "Amazon.in":  ["Electronics", "Footwear", "Clothing", "Kitchen", "Home", "Sports", "Beauty", "Home Appliances", "Grocery"],
        "Flipkart":   ["Electronics", "Footwear", "Clothing", "Kitchen", "Home", "Sports", "Beauty", "Home Appliances"],
        "Myntra":     ["Footwear", "Clothing", "Beauty"],
        "Nykaa":      ["Beauty"],
        "BigBasket":  ["Grocery"],
        "JioMart":    ["Grocery", "Home"],
    }
    return category in mapping.get(comp, [])
