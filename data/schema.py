"""
data/schema.py
Pydantic models for all data objects in the pricing pipeline.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ── Raw data inputs ───────────────────────────────────────────────────────────

class SalesRecord(BaseModel):
    order_id: str
    product_id: str
    category: str
    price: float = Field(gt=0)
    quantity: int = Field(gt=0)
    discount_pct: float = Field(ge=0, le=1, default=0.0)
    timestamp: datetime
    user_segment: Optional[str] = "standard"   # loyal, new, vip, standard

    @property
    def revenue(self) -> float:
        return self.price * self.quantity * (1 - self.discount_pct)


class InventoryRecord(BaseModel):
    product_id: str
    stock_quantity: int = Field(ge=0)
    reorder_point: int = Field(ge=0)
    days_of_supply: Optional[float] = None
    warehouse_id: str = "main"
    updated_at: datetime


class CompetitorPrice(BaseModel):
    product_id: str
    competitor_name: str
    competitor_price: float = Field(gt=0)
    url: Optional[str] = None
    scraped_at: datetime


class UserEvent(BaseModel):
    event_type: str                        # view, add_to_cart, purchase, abandon
    product_id: str
    user_id: Optional[str] = None
    session_id: str
    price_shown: float
    timestamp: datetime


# ── Feature vectors ───────────────────────────────────────────────────────────

class ProductFeatures(BaseModel):
    product_id: str
    base_price: float
    category: str

    # Demand signals
    views_7d: int = 0
    add_to_cart_7d: int = 0
    purchases_7d: int = 0
    conversion_rate_7d: float = 0.0

    # Inventory signals
    stock_quantity: int = 0
    days_of_supply: float = 30.0
    inventory_urgency: float = 0.0        # 0=plenty, 1=critical

    # Competitor signals
    competitor_avg_price: Optional[float] = None
    price_vs_competitor: Optional[float] = None    # ratio: our_price / comp_price

    # Temporal signals
    hour_of_day: int = 12
    day_of_week: int = 1
    is_weekend: bool = False
    days_to_payday: int = 15

    # Computed elasticity (from model)
    price_elasticity: Optional[float] = None


# ── API request / response ────────────────────────────────────────────────────

class PricingRequest(BaseModel):
    product_id: str
    user_segment: str = "standard"
    inventory: Optional[int] = None       # Override live inventory if provided
    context: Optional[dict] = None        # Extra context (campaign, channel, etc.)


class PricingResponse(BaseModel):
    product_id: str
    recommended_price: float
    base_price: float
    price_change_pct: float
    confidence: float = Field(ge=0, le=1)
    reason: str
    guardrail_applied: bool = False
    model_version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BatchPricingRequest(BaseModel):
    requests: list[PricingRequest]


class BatchPricingResponse(BaseModel):
    results: list[PricingResponse]
    total_products: int
    processing_time_ms: float
