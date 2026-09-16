"""
Changed from truncate+reload to incremental upsert (INSERT ... ON DUPLICATE
KEY UPDATE). Re-running this after new/updated CSVs only inserts new rows and
updates changed ones — existing history is never wiped. Also added basic
null/duplicate key validation before loading.
"""
import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "bizpulse")

engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


def build_date_dim(all_dates: pd.Series) -> pd.DataFrame:
    start, end = all_dates.min(), all_dates.max()
    dates = pd.date_range(start, end, freq="D")
    df = pd.DataFrame({"full_date": dates})
    df["date_key"] = df["full_date"].dt.strftime("%Y%m%d").astype(int)
    df["day_of_week"] = df["full_date"].dt.day_name()
    df["month_num"] = df["full_date"].dt.month
    df["month_name"] = df["full_date"].dt.month_name()
    df["quarter_num"] = df["full_date"].dt.quarter
    df["year_num"] = df["full_date"].dt.year
    df["is_weekend"] = df["full_date"].dt.dayofweek >= 5
    return df[["date_key", "full_date", "day_of_week", "month_num", "month_name",
               "quarter_num", "year_num", "is_weekend"]]


def to_date_key(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series).dt.strftime("%Y%m%d").astype(int)


def validate(df: pd.DataFrame, key_cols: list, label: str) -> pd.DataFrame:
    before = len(df)
    df = df.dropna(subset=key_cols)
    if len(df) < before:
        print(f"  [warn] {label}: dropped {before - len(df)} rows with null {key_cols}")
    before = len(df)
    df = df.drop_duplicates(subset=key_cols, keep="last")
    if len(df) < before:
        print(f"  [warn] {label}: dropped {before - len(df)} duplicate rows on {key_cols}")
    return df


def upsert_dataframe(df: pd.DataFrame, table: str, key_cols: list):
    if df.empty:
        print(f"  {table}: nothing to load")
        return

    df = df.replace({np.nan: None, pd.NaT: None})
    cols = list(df.columns)
    col_list = ", ".join(f"`{c}`" for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    update_cols = [c for c in cols if c not in key_cols]
    sql = f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders})"
    if update_cols:
        update_clause = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in update_cols)
        sql += f" ON DUPLICATE KEY UPDATE {update_clause}"

    data = [tuple(row) for row in df.itertuples(index=False, name=None)]

    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        cursor.executemany(sql, data)
        raw_conn.commit()
        cursor.close()
    finally:
        raw_conn.close()

    print(f"  upserted {len(df):,} rows -> {table}")


def main():
    print("Reading CSVs from data/ ...")
    customers = pd.read_csv("data/customers.csv", parse_dates=["signup_date"])
    products = pd.read_csv("data/products.csv")
    campaigns = pd.read_csv("data/marketing_campaigns.csv", parse_dates=["start_date", "end_date"])
    orders = pd.read_csv("data/sales_orders.csv", parse_dates=["order_date"])
    inventory = pd.read_csv("data/inventory_stock.csv", parse_dates=["snapshot_date"])
    spend = pd.read_csv("data/marketing_daily_spend.csv", parse_dates=["date"])
    tickets = pd.read_csv("data/support_tickets.csv", parse_dates=["created_date"])

    print("Validating (null/duplicate keys)...")
    customers = validate(customers, ["customer_id"], "customers")
    products = validate(products, ["product_id"], "products")
    campaigns = validate(campaigns, ["campaign_id"], "campaigns")
    orders = validate(orders, ["order_id"], "sales_orders")
    tickets = validate(tickets, ["ticket_id"], "support_tickets")
    inventory = validate(inventory, ["snapshot_date", "product_id", "warehouse_location"], "inventory_stock")
    spend = validate(spend, ["date", "campaign_id"], "marketing_daily_spend")

    print("Building date dimension...")
    all_dates = pd.concat([
        orders["order_date"], inventory["snapshot_date"],
        spend["date"], tickets["created_date"],
    ])
    dim_date = build_date_dim(all_dates)

    print("Computing derived fact columns (cogs, gross_margin, SLA flag, reorder flag)...")
    cost_lookup = products.set_index("product_id")["unit_cost"]

    orders["date_key"] = to_date_key(orders["order_date"])
    orders["revenue"] = orders["total_amount"]
    orders["cogs"] = orders["quantity"] * orders["product_id"].map(cost_lookup)
    orders["gross_margin"] = orders["revenue"] - orders["cogs"]
    fact_sales = orders[[
        "order_id", "order_date", "date_key", "customer_id", "product_id",
        "quantity", "unit_price", "discount", "revenue", "cogs", "gross_margin",
        "payment_method", "channel", "order_status",
    ]]

    inventory["date_key"] = to_date_key(inventory["snapshot_date"])
    inventory["is_below_reorder"] = inventory["closing_stock"] < inventory["reorder_level"]
    fact_inventory = inventory[[
        "snapshot_date", "date_key", "product_id", "warehouse_location",
        "stock_in", "stock_out", "closing_stock", "reorder_level", "is_below_reorder",
    ]]

    spend["date_key"] = to_date_key(spend["date"])
    fact_marketing = spend.rename(columns={"date": "spend_date"})[[
        "spend_date", "date_key", "campaign_id", "platform",
        "impressions", "clicks", "spend", "leads_generated", "conversions",
    ]]

    tickets["date_key"] = to_date_key(tickets["created_date"])
    tickets["is_sla_breached"] = tickets["resolution_time_hours"] > 48
    fact_support = tickets[[
        "ticket_id", "created_date", "date_key", "customer_id", "related_order_id",
        "channel", "category", "priority", "status", "resolution_time_hours",
        "satisfaction_rating", "is_sla_breached",
    ]]

    print("\nUpserting dimensions...")
    upsert_dataframe(dim_date, "dim_date", ["date_key"])
    upsert_dataframe(customers, "dim_customer", ["customer_id"])
    upsert_dataframe(products, "dim_product", ["product_id"])
    upsert_dataframe(campaigns, "dim_campaign", ["campaign_id"])

    print("\nUpserting facts...")
    upsert_dataframe(fact_sales, "fact_sales", ["order_id"])
    upsert_dataframe(fact_inventory, "fact_inventory", ["snapshot_date", "product_id", "warehouse_location"])
    upsert_dataframe(fact_marketing, "fact_marketing_spend", ["spend_date", "campaign_id"])
    upsert_dataframe(fact_support, "fact_support_tickets", ["ticket_id"])

    print("\nDone. Warehouse is up to date (existing rows updated, new rows added, nothing wiped).")
    print("Connect Power BI to this MySQL database and point at the dim_/fact_/vw_ tables.")


if __name__ == "__main__":
    main()
