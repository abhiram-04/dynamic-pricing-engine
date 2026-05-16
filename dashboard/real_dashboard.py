"""
dashboard/real_dashboard.py
ShopSmart India — Real-world pricing dashboard.
Shows actual product catalogue with live AI pricing recommendations.

Run with:
    streamlit run dashboard/real_dashboard.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime

from data.catalogue import ALL_PRODUCTS, CATEGORIES
from data.real_ingestion import (
    generate_real_sales_data,
    generate_real_inventory_data,
    generate_real_competitor_data,
)
from features.pipeline import FeaturePipeline
from features.store import FeatureStore
from models.elasticity import ElasticityModel
from models.demand import DemandForecaster
from models.optimizer import PriceOptimizer
from api.guardrails import PriceGuardrails
from config.settings import settings

st.set_page_config(
    page_title="ShopSmart India — AI Pricing",
    page_icon="🛒",
    layout="wide",
)

st.title("🛒 ShopSmart India — AI Dynamic Pricing Dashboard")
st.markdown("Real-time price optimisation across your product catalogue")

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_data():
    sales     = generate_real_sales_data(days_back=90)
    inventory = generate_real_inventory_data()
    comps     = generate_real_competitor_data()
    return sales, inventory, comps

@st.cache_resource
def load_models():
    em = ElasticityModel()
    df = DemandForecaster()
    if os.path.exists(settings.ELASTICITY_MODEL_PATH):
        em.load()
    if os.path.exists(settings.DEMAND_MODEL_PATH):
        df.load()
    return em, df

sales_df, inventory_df, competitor_df = load_data()
pipeline = FeaturePipeline(sales_df, inventory_df, competitor_df)
elasticity_model, demand_forecaster = load_models()
optimizer = PriceOptimizer(elasticity_model, demand_forecaster, PriceGuardrails())

# ── KPI row ───────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
total_rev = sales_df["revenue"].sum()
total_profit = sales_df["profit"].sum()
avg_margin = total_profit / total_rev * 100
top_product = sales_df.groupby("product_id")["revenue"].sum().idxmax()
top_name = next((p.name[:30] for p in ALL_PRODUCTS if p.id == top_product), top_product)

col1.metric("90-day Revenue",    f"₹{total_rev/1e6:.1f}M")
col2.metric("Gross Profit",      f"₹{total_profit/1e6:.1f}M")
col3.metric("Avg Margin",        f"{avg_margin:.1f}%")
col4.metric("Active Products",   len(ALL_PRODUCTS))
col5.metric("Top Seller",        top_name)

st.divider()

# ── AI pricing recommendations table ─────────────────────────────────────────
st.subheader("AI Price Recommendations — Live")

rows = []
for product in ALL_PRODUCTS:
    try:
        feat = pipeline.build_features(product.id)
        feat.base_price = product.base_price
        resp = optimizer.optimise(feat)

        comp = competitor_df[competitor_df["product_id"] == product.id]
        comp_avg = comp["competitor_price"].mean() if len(comp) > 0 else None

        rows.append({
            "Product":        product.name[:45],
            "Category":       product.category,
            "Your Price":     f"₹{product.base_price:,.0f}",
            "AI Price":       f"₹{resp.recommended_price:,.0f}",
            "Change %":       f"{resp.price_change_pct:+.1f}%",
            "Competitor Avg": f"₹{comp_avg:,.0f}" if comp_avg else "N/A",
            "Margin":         f"{product.margin_pct:.0f}%",
            "Stock":          next((r.stock_quantity for _, r in inventory_df.iterrows()
                                   if r.product_id == product.id), 0),
            "Confidence":     f"{resp.confidence:.0%}",
            "Guardrail":      "Yes" if resp.guardrail_applied else "No",
            "Reason":         resp.reason[:60],
        })
    except Exception as e:
        pass

rec_df = pd.DataFrame(rows)

def color_change(val):
    if "+" in str(val): return "color: #0F6E56; font-weight: bold"
    if "-" in str(val): return "color: #993C1D; font-weight: bold"
    return ""

st.dataframe(
    rec_df.style.applymap(color_change, subset=["Change %"]),
    use_container_width=True,
    height=420,
)

# ── Revenue by category ───────────────────────────────────────────────────────
st.subheader("Revenue by Category — Last 90 days")
cat_rev = sales_df.groupby("category")["revenue"].sum().reset_index()
cat_rev.columns = ["Category", "Revenue"]
cat_rev = cat_rev.sort_values("Revenue", ascending=False)

fig = px.bar(
    cat_rev, x="Category", y="Revenue",
    color="Revenue",
    color_continuous_scale=["#9FE1CB", "#1D9E75", "#085041"],
    labels={"Revenue": "Revenue (₹)"},
)
fig.update_layout(coloraxis_showscale=False, showlegend=False)
fig.update_traces(hovertemplate="₹%{y:,.0f}<extra></extra>")
st.plotly_chart(fig, use_container_width=True)

# ── Daily revenue trend ───────────────────────────────────────────────────────
st.subheader("Daily Revenue Trend")
sales_df["date"] = pd.to_datetime(sales_df["timestamp"]).dt.date
daily = sales_df.groupby("date")["revenue"].sum().reset_index()
daily.columns = ["Date", "Revenue"]

fig2 = px.line(daily, x="Date", y="Revenue",
               labels={"Revenue": "Revenue (₹)"},
               color_discrete_sequence=["#1D9E75"])
fig2.update_traces(line_width=1.5)
st.plotly_chart(fig2, use_container_width=True)

# ── Inventory urgency ─────────────────────────────────────────────────────────
st.subheader("Inventory Urgency")
inv_df = inventory_df.copy()
inv_df["urgency_pct"] = (
    1.0 - (inv_df["stock_quantity"] / (inv_df["reorder_point"] * 3))
).clip(0, 1) * 100

fig3 = px.bar(
    inv_df.sort_values("urgency_pct", ascending=False),
    x="product_id", y="urgency_pct",
    color="urgency_pct",
    color_continuous_scale=["#1D9E75", "#EF9F27", "#E24B4A"],
    range_color=[0, 100],
    labels={"urgency_pct": "Urgency %", "product_id": "Product"},
)
fig3.add_hline(y=70, line_dash="dash", line_color="#E24B4A",
               annotation_text="Reorder zone (70%)")
st.plotly_chart(fig3, use_container_width=True)

# ── Competitor comparison ─────────────────────────────────────────────────────
st.subheader("Your Price vs Competitor Average")
comp_summary = []
for product in ALL_PRODUCTS:
    comp = competitor_df[competitor_df["product_id"] == product.id]
    if len(comp) > 0:
        comp_avg = comp["competitor_price"].mean()
        comp_summary.append({
            "Product": product.name[:35],
            "Your Price": product.base_price,
            "Competitor Avg": round(comp_avg, 0),
            "Difference %": round((product.base_price - comp_avg) / comp_avg * 100, 1),
        })

cs_df = pd.DataFrame(comp_summary)
fig4 = go.Figure()
fig4.add_trace(go.Bar(name="Your Price",       x=cs_df["Product"], y=cs_df["Your Price"],
                      marker_color="#7F77DD"))
fig4.add_trace(go.Bar(name="Competitor Avg",   x=cs_df["Product"], y=cs_df["Competitor Avg"],
                      marker_color="#B4B2A9"))
fig4.update_layout(barmode="group", xaxis_tickangle=-30, legend=dict(orientation="h"))
st.plotly_chart(fig4, use_container_width=True)

st.caption("ShopSmart India AI Pricing Engine · Powered by XGBoost + Prophet · Refreshes every 10 min")
