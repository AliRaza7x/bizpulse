# BizPulse — Unified Business Data Warehouse

BizPulse pulls together data from the four parts of a small online business —
**Sales, Inventory, Marketing, and Customer Support** — into one MySQL data
warehouse. Instead of checking Facebook orders, stock sheets, ad spend, and
support messages separately, everything lands in one place: revenue, cost,
stock levels, campaign performance, and support tickets — ready to connect to
Power BI for a live dashboard.

It ships with realistic sample data (300 customers, 1,500 orders, 60 products,
7,000+ inventory snapshots, 25 marketing campaigns, 450 support tickets) that
are all linked to each other by shared IDs, so the numbers actually add up
when you build reports.

## What's in here

```
bizpulse/
├── data/                      # CSV data files (sales, inventory, marketing, support)
├── sql/create_warehouse.sql   # Creates the MySQL database + all tables + views
├── scripts/
│   ├── generate_data.py       # (Re)generates the CSVs in data/
│   └── load_to_mysql.py       # Loads the CSVs into the MySQL warehouse
├── docker-compose.yml         # Local MySQL + Adminer (DB viewer)
├── requirements.txt
└── .env.example
```

## How to run it

```bash
# 1. Set up Python
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Start MySQL locally
cp .env.example .env
docker compose up -d

# 3. Create the warehouse (tables + views)
mysql -h 127.0.0.1 -u root -p bizpulse < sql/create_warehouse.sql
# (password is whatever you set in .env, default: bizpulse_root_pw)

# 4. Load the data
python scripts/load_to_mysql.py
```

That's it — the warehouse is built and populated. Open Adminer at
`http://localhost:8080` (server: `mysql`, user: `root`) to browse the tables,
or connect Power BI directly to `127.0.0.1:3306`, database `bizpulse`.

Point Power BI at the `dim_*`, `fact_*`, and `vw_*` tables/views — the `vw_`
ones (`vw_monthly_revenue`, `vw_product_performance`, `vw_stock_health`,
`vw_campaign_roi`, `vw_support_sla`) are pre-built summaries so the dashboard
doesn't need to recompute revenue/margin/SLA logic from scratch.

## Regenerating or resizing the sample data

```bash
python scripts/generate_data.py --customers 500 --days 180
```

Then re-run `python scripts/load_to_mysql.py` to reload the warehouse.

## What's next

Once the warehouse and dashboard are working, Kafka/PySpark/Airflow can be
layered in later if the data volume or need for real-time updates actually
calls for it — not needed to get the first working version live.
