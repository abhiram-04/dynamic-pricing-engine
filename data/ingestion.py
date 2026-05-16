"""
data/ingestion.py
Pulls sales history, inventory levels, and competitor prices
from various sources and normalises into the pipeline schema.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
from faker import Faker

from data.schema import SalesRecord, InventoryRecord, CompetitorPrice

fake = Faker()


# ── Synthetic data generator (for dev / demo) ─────────────────────────────────

CATEGORIES = ["electronics", "clothing", "home", "sports", "beauty"]
SEGMENTS = ["standard", "new", "loyal", "vip"]

def generate_sales_data(
    n_products: int = 50,
    n_records: int = 10_000,
    days_back: int = 180,
) -> pd.DataFrame:
    """
    Generate realistic synthetic sales data for model training.
    Includes natural price elasticity patterns per category.
    """
    np.random.seed(42)

    products = [f"SKU-{i:03d}" for i in range(n_products)]
    base_prices = {p: round(np.random.uniform(5, 300), 2) for p in products}
    categories = {p: np.random.choice(CATEGORIES) for p in products}

    # Elasticity varies by category: electronics are more elastic than beauty
    elasticity_by_category = {
        "electronics": -2.1,
        "clothing":    -1.5,
        "home":        -1.2,
        "sports":      -1.8,
        "beauty":      -0.9,
    }

    records = []
    for _ in range(n_records):
        product_id = np.random.choice(products)
        base = base_prices[product_id]
        cat = categories[product_id]
        elasticity = elasticity_by_category[cat]

        # Price varies ±25% from base
        price_factor = np.random.uniform(0.75, 1.25)
        price = round(base * price_factor, 2)

        # Quantity responds to price via elasticity
        base_qty = np.random.poisson(lam=5)
        qty_adjustment = (price_factor - 1.0) * elasticity
        quantity = max(1, int(base_qty * (1 + qty_adjustment)))

        # Timestamp spread over lookback window
        days_ago = np.random.uniform(0, days_back)
        ts = datetime.utcnow() - timedelta(days=days_ago)

        records.append({
            "order_id":     fake.uuid4(),
            "product_id":   product_id,
            "category":     cat,
            "price":        price,
            "quantity":     quantity,
            "discount_pct": round(np.random.choice([0, 0, 0, 0.05, 0.10, 0.15], p=[0.6, 0.1, 0.1, 0.08, 0.07, 0.05]), 2),
            "timestamp":    ts,
            "user_segment": np.random.choice(SEGMENTS, p=[0.55, 0.25, 0.15, 0.05]),
        })

    df = pd.DataFrame(records)
    logger.info(f"Generated {len(df)} synthetic sales records for {n_products} products")
    return df


def generate_inventory_data(n_products: int = 50) -> pd.DataFrame:
    """Generate synthetic inventory snapshot."""
    np.random.seed(99)
    products = [f"SKU-{i:03d}" for i in range(n_products)]
    records = []
    for p in products:
        stock = int(np.random.exponential(scale=80))
        reorder_pt = int(np.random.uniform(10, 30))
        records.append({
            "product_id":     p,
            "stock_quantity": stock,
            "reorder_point":  reorder_pt,
            "days_of_supply": round(stock / max(1, np.random.uniform(1, 8)), 1),
            "updated_at":     datetime.utcnow(),
        })
    return pd.DataFrame(records)


def generate_competitor_data(n_products: int = 50) -> pd.DataFrame:
    """Generate synthetic competitor price data."""
    np.random.seed(7)
    products = [f"SKU-{i:03d}" for i in range(n_products)]
    competitors = ["CompetitorA", "CompetitorB", "CompetitorC"]
    records = []
    for p in products:
        for comp in np.random.choice(competitors, size=np.random.randint(1, 4), replace=False):
            # Competitor prices cluster within ±20% of a notional market price
            market_price = np.random.uniform(5, 300)
            records.append({
                "product_id":       p,
                "competitor_name":  comp,
                "competitor_price": round(market_price * np.random.uniform(0.85, 1.15), 2),
                "scraped_at":       datetime.utcnow(),
            })
    return pd.DataFrame(records)


# ── Production connectors (stub — replace with real sources) ──────────────────

class DatabaseIngestion:
    """Connects to a PostgreSQL orders table and returns a DataFrame."""

    def __init__(self, connection_string: str):
        self.conn_str = connection_string

    def fetch_sales(self, days_back: int = 90) -> pd.DataFrame:
        from sqlalchemy import create_engine, text
        engine = create_engine(self.conn_str)
        query = text("""
            SELECT order_id, product_id, category, price, quantity,
                   discount_pct, created_at AS timestamp, user_segment
            FROM orders
            WHERE created_at >= NOW() - INTERVAL ':days days'
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn, params={"days": days_back})


class CompetitorScraper:
    """
    Lightweight competitor price scraper.
    Replace `_parse_price` with site-specific CSS selectors.
    """

    def __init__(self, urls: list[str]):
        self.urls = urls

    def scrape_all(self) -> list[CompetitorPrice]:
        import requests
        from bs4 import BeautifulSoup
        results = []
        for url in self.urls:
            try:
                resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(resp.text, "html.parser")
                price = self._parse_price(soup)
                if price:
                    results.append(CompetitorPrice(
                        product_id=self._extract_product_id(url),
                        competitor_name=self._extract_domain(url),
                        competitor_price=price,
                        url=url,
                        scraped_at=datetime.utcnow(),
                    ))
            except Exception as e:
                logger.warning(f"Scrape failed for {url}: {e}")
        return results

    def _parse_price(self, soup) -> Optional[float]:
        # Override with site-specific selectors
        el = soup.select_one('[itemprop="price"], .price, #price')
        if el:
            raw = el.get("content") or el.text
            cleaned = "".join(c for c in raw if c.isdigit() or c == ".")
            return float(cleaned) if cleaned else None
        return None

    def _extract_product_id(self, url: str) -> str:
        return url.split("/")[-1].split("?")[0]

    def _extract_domain(self, url: str) -> str:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
