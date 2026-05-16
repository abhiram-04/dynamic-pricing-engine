"""
dashboard/app.py
Streamlit monitoring dashboard for the dynamic pricing engine.

Run with:
    streamlit run dashboard/app.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data.ingestion import (
    generate_sales_data,
    generate_inventory_data,
    generate_competitor_data,
)
from features.pipeline import FeaturePipeline
from features.store import FeatureStore


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dynamic Pricing Engine",
    page_icon="💰",
    layout="wide",
)

st.title("💰 Dynamic Pricing Engine — Dashboard")
st.markdown("Real-time monitoring of price recommendations, demand signals, and revenue impact.")

# ── Load data (cached) ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    sales_df      = generate_sales_data(n_products=30, n_records=6_000)
    inventory_df  = generate_inventory_data(n_products=30)
    competitor_df = generate_competitor_data(n_products=30)
    return sales_df, inventory_df, competitor_df


sales_df, inventory_df, competitor_df = load_data()
pipeline = FeaturePipeline(sales_df, inventory_df, competitor_df)

# ── KPI cards ─────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

total_revenue = (sales_df["price"] * sales_df["quantity"]).sum()
avg_price     = sales_df["price"].mean()
n_products    = sales_df["product_id"].nunique()
top_category  = sales_df.groupby("category")["quantity"].sum().idxmax()

col1.metric("Total Revenue",       f"${total_revenue:,.0f}")
col2.metric("Avg Selling Price",   f"${avg_price:.2f}")
col3.metric("Active Products",     n_products)
col4.metric("Top Category",        top_category.title())

st.divider()

# ── Revenue over time ─────────────────────────────────────────────────────────
st.subheader("Revenue over Time")
sales_df["date"] = pd.to_datetime(sales_df["timestamp"]).dt.floor("D")
daily = (
    sales_df.assign(revenue=sales_df["price"] * sales_df["quantity"])
    .groupby("date")["revenue"]
    .sum()
    .reset_index()
)
fig = px.line(daily, x="date", y="revenue", title="Daily Revenue",
              labels={"revenue": "Revenue ($)", "date": "Date"})
fig.update_traces(line_color="#7C3AED")
st.plotly_chart(fig, use_container_width=True)

# ── Price distribution by category ────────────────────────────────────────────
st.subheader("Price Distribution by Category")
fig2 = px.box(
    sales_df, x="category", y="price",
    color="category",
    labels={"price": "Price ($)", "category": "Category"},
    color_discrete_sequence=px.colors.qualitative.Vivid,
)
fig2.update_layout(showlegend=False)
st.plotly_chart(fig2, use_container_width=True)

# ── Price elasticity by category ──────────────────────────────────────────────
st.subheader("Estimated Price Elasticity by Category")

@st.cache_data(ttl=600)
def compute_elasticity_by_category():
    rows = []
    for cat in ["electronics", "clothing", "home", "sports", "beauty"]:
        cat_sales = sales_df[sales_df["category"] == cat]
        if len(cat_sales) < 30:
            continue
        # Simple OLS log-log regression: log(Q) ~ log(P)
        log_p = np.log(cat_sales["price"].clip(lower=0.01))
        log_q = np.log(cat_sales["quantity"].clip(lower=0.01))
        elasticity = np.polyfit(log_p, log_q, 1)[0]
        rows.append({"category": cat.title(), "elasticity": round(elasticity, 2)})
    return pd.DataFrame(rows)

elas_df = compute_elasticity_by_category()
fig3 = px.bar(
    elas_df, x="category", y="elasticity",
    color="elasticity",
    color_continuous_scale=["#ef4444", "#f97316", "#22c55e"],
    labels={"elasticity": "Elasticity (ε)", "category": "Category"},
    title="Price Elasticity (more negative = more price-sensitive)",
)
fig3.add_hline(y=-1, line_dash="dash", line_color="gray",
               annotation_text="Unit elastic (ε=−1)")
st.plotly_chart(fig3, use_container_width=True)

# ── Inventory urgency ─────────────────────────────────────────────────────────
st.subheader("Inventory Urgency by Product")

inv_display = inventory_df.copy()
inv_display["urgency"] = (
    1.0 - (inv_display["stock_quantity"] / (inv_display["reorder_point"] * 3))
).clip(0, 1).round(2)
inv_display = inv_display.sort_values("urgency", ascending=False).head(20)

fig4 = px.bar(
    inv_display, x="product_id", y="urgency",
    color="urgency",
    color_continuous_scale=["#22c55e", "#f97316", "#ef4444"],
    range_color=[0, 1],
    labels={"urgency": "Urgency (0=OK, 1=Critical)", "product_id": "Product"},
    title="Top 20 products by inventory urgency",
)
st.plotly_chart(fig4, use_container_width=True)

# ── Feature store stats ───────────────────────────────────────────────────────
st.subheader("Feature Store Status")
try:
    store = FeatureStore()
    stats = store.stats()
    st.json(stats)
except Exception as e:
    st.warning(f"Feature store not available: {e}")

st.caption("Dashboard auto-refreshes every 5 minutes. Data sourced from synthetic generator.")
