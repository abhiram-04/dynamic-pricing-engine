# Dynamic Pricing Engine

AI-powered real-time pricing system for e-commerce. Combines price elasticity modelling, demand forecasting, and competitor intelligence to optimise prices and maximise revenue.

## Project Structure

```
dynamic_pricing_engine/
├── config/               # Configuration files
│   └── settings.py
├── data/                 # Data ingestion & storage
│   ├── ingestion.py      # Pull sales, inventory, competitor data
│   └── schema.py         # Pydantic data models
├── features/             # Feature engineering
│   ├── pipeline.py       # Batch + streaming feature pipeline
│   └── store.py          # Feature store (Redis-backed)
├── models/               # ML models
│   ├── elasticity.py     # Price elasticity (XGBoost)
│   ├── demand.py         # Demand forecasting (Prophet)
│   └── optimizer.py      # Price optimizer (scipy / RL)
├── api/                  # FastAPI serving layer
│   ├── main.py           # App entry point
│   ├── routes.py         # /price endpoint
│   └── guardrails.py     # Price floor/ceiling rules
├── dashboard/            # Streamlit monitoring dashboard
│   └── app.py
├── tests/                # Unit + integration tests
│   ├── test_elasticity.py
│   ├── test_optimizer.py
│   └── test_api.py
├── notebooks/            # EDA + model exploration
│   └── 01_eda.ipynb
├── scripts/              # One-off scripts
│   ├── train.py          # Train all models
│   └── backtest.py       # Revenue backtest
├── requirements.txt
└── docker-compose.yml
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start Redis (feature store) and Kafka (streaming)
docker-compose up -d

# 3. Train models on historical data
python scripts/train.py --data data/sample_sales.csv

# 4. Start the pricing API
uvicorn api.main:app --reload --port 8000

# 5. Launch monitoring dashboard
streamlit run dashboard/app.py
```

## API Usage

```bash
# Get optimised price for a product
curl -X POST http://localhost:8000/price \
  -H "Content-Type: application/json" \
  -d '{"product_id": "SKU-001", "user_segment": "loyal", "inventory": 45}'

# Response
{
  "product_id": "SKU-001",
  "recommended_price": 34.99,
  "base_price": 29.99,
  "price_change_pct": 16.7,
  "confidence": 0.87,
  "reason": "Low inventory + high demand signal"
}
```

## Business KPIs Targeted

| Metric | Baseline | Target |
|--------|----------|--------|
| Revenue per session | $4.20 | $4.70 (+12%) |
| Gross margin | 38% | 42% (+4pp) |
| Stockout rate | 8% | 4% (-50%) |
| Price elasticity RMSE | — | < 0.15 |

## Tech Stack

- **ML**: XGBoost, Prophet, scikit-learn, scipy
- **API**: FastAPI, Pydantic, uvicorn
- **Streaming**: Kafka, Redis
- **Orchestration**: Apache Airflow
- **Monitoring**: MLflow, Streamlit
- **Storage**: PostgreSQL, Redis
