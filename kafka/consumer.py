"""
Listens on the `sales_orders` Kafka topic and upserts each incoming order into
fact_sales as it arrives, using the same ON DUPLICATE KEY UPDATE approach as
scripts/load_to_mysql.py. Assumes dim_customer/dim_product are already loaded.
"""
import json
import os

import pandas as pd
from dotenv import load_dotenv
from kafka import KafkaConsumer
from sqlalchemy import create_engine

load_dotenv()

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
TOPIC = "sales_orders"

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "bizpulse")

engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
cost_lookup = pd.read_csv("data/products.csv").set_index("product_id")["unit_cost"]


def upsert_order(order: dict):
    order_date = pd.to_datetime(order["order_date"])
    quantity = order["quantity"]
    revenue = order["total_amount"]
    cogs = quantity * cost_lookup.get(order["product_id"], 0)

    row = {
        "order_id": order["order_id"],
        "order_date": order_date,
        "date_key": int(order_date.strftime("%Y%m%d")),
        "customer_id": order["customer_id"],
        "product_id": order["product_id"],
        "quantity": quantity,
        "unit_price": order["unit_price"],
        "discount": order["discount"],
        "revenue": revenue,
        "cogs": cogs,
        "gross_margin": revenue - cogs,
        "payment_method": order["payment_method"],
        "channel": order["channel"],
        "order_status": order["order_status"],
    }

    cols = list(row.keys())
    col_list = ", ".join(f"`{c}`" for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    update_cols = [c for c in cols if c != "order_id"]
    update_clause = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in update_cols)
    sql = f"INSERT INTO `fact_sales` ({col_list}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_clause}"

    raw_conn = engine.raw_connection()
    try:
        cursor = raw_conn.cursor()
        cursor.execute(sql, tuple(row.values()))
        raw_conn.commit()
        cursor.close()
    finally:
        raw_conn.close()


def main():
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        group_id="bizpulse-sales-consumer",
    )
    for message in consumer:
        order = message.value
        upsert_order(order)
        print(f"loaded {order['order_id']}")


if __name__ == "__main__":
    main()
