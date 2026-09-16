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
├── docker-compose.yml         # Local MySQL + Adminer + Kafka
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

## Streaming with Kafka (optional, real-time path)

`kafka/producer.py` streams rows from `data/sales_orders.csv` into a Kafka
topic one at a time, simulating live orders. `kafka/consumer.py` listens on
that topic and upserts each order into `fact_sales` as it arrives, instead of
waiting for the next batch run of `load_to_mysql.py`.

```bash
docker compose up -d          # now also starts a local Kafka broker on :9092
python kafka/consumer.py      # run this first, in one terminal — it waits for messages
python kafka/producer.py      # run this in a second terminal — it starts sending orders
```

## Heavier processing with PySpark (optional, for larger data volumes)

`spark/transform_spark.py` is a Spark version of the transform logic in
`load_to_mysql.py` — same cogs/margin/SLA calculations, but computed as Spark
DataFrame operations that can scale across a cluster once a single day's data
no longer fits comfortably in memory on one machine.

```bash
pip install pyspark
spark-submit --packages mysql:mysql-connector-java:8.0.33 spark/transform_spark.py
```

Note: this writes in append mode via Spark's JDBC writer, which does not
upsert like `load_to_mysql.py` does — running it twice on the same data will
duplicate rows unless you truncate the target tables first. It's meant as a
starting point for a bigger-data version of the pipeline, not a drop-in
replacement for the incremental loader yet.

## What's next

Airflow (scheduling/orchestration) can still be layered in later if you want
these steps running automatically instead of by hand.
