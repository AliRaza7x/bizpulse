import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

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


def truncate_all():
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in ["fact_sales", "fact_inventory", "fact_marketing_spend",
                  "fact_support_tickets", "dim_customer", "dim_product",
                  "dim_campaign", "dim_date"]:
            conn.execute(text(f"TRUNCATE TABLE {t}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))


def main():
    print("Reading CSVs from data/ ...")
    customers = pd.read_csv("data/customers.csv", parse_dates=["signup_date"])
    products = pd.read_csv("data/products.csv")
    campaigns = pd.read_csv("data/marketing_campaigns.csv", parse_dates=["start_date", "end_date"])
    orders = pd.read_csv("data/sales_orders.csv", parse_dates=["order_date"])
    inventory = pd.read_csv("data/inventory_stock.csv", parse_dates=["snapshot_date"])
    spend = pd.read_csv("data/marketing_daily_spend.csv", parse_dates=["date"])
    tickets = pd.read_csv("data/support_tickets.csv", parse_dates=["created_date"])

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

    print("Clearing existing warehouse data...")
    truncate_all()

    print("Loading dimensions...")
    dim_date.to_sql("dim_date", engine, if_exists="append", index=False, chunksize=1000)
    customers.to_sql("dim_customer", engine, if_exists="append", index=False, chunksize=1000)
    products.to_sql("dim_product", engine, if_exists="append", index=False, chunksize=1000)
    campaigns.to_sql("dim_campaign", engine, if_exists="append", index=False, chunksize=1000)

    print("Loading facts...")
    fact_sales.to_sql("fact_sales", engine, if_exists="append", index=False, chunksize=1000)
    fact_inventory.to_sql("fact_inventory", engine, if_exists="append", index=False, chunksize=1000)
    fact_marketing.to_sql("fact_marketing_spend", engine, if_exists="append", index=False, chunksize=1000)
    fact_support.to_sql("fact_support_tickets", engine, if_exists="append", index=False, chunksize=1000)

    print("\nDone. Warehouse loaded:")
    print(f"  dim_customer          {len(customers):>6,}")
    print(f"  dim_product           {len(products):>6,}")
    print(f"  dim_campaign          {len(campaigns):>6,}")
    print(f"  dim_date              {len(dim_date):>6,}")
    print(f"  fact_sales            {len(fact_sales):>6,}")
    print(f"  fact_inventory        {len(fact_inventory):>6,}")
    print(f"  fact_marketing_spend  {len(fact_marketing):>6,}")
    print(f"  fact_support_tickets  {len(fact_support):>6,}")
    print("\nConnect Power BI to this MySQL database and point at the dim_/fact_/vw_ tables.")


if __name__ == "__main__":
    main()
