import os

from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "bizpulse")

JDBC_URL = f"jdbc:mysql://{DB_HOST}:{DB_PORT}/{DB_NAME}"
JDBC_PROPS = {"user": DB_USER, "password": DB_PASSWORD, "driver": "com.mysql.cj.jdbc.Driver"}


def main():
    spark = SparkSession.builder.appName("bizpulse-transform").getOrCreate()

    orders = spark.read.csv("data/sales_orders.csv", header=True, inferSchema=True)
    products = spark.read.csv("data/products.csv", header=True, inferSchema=True)
    inventory = spark.read.csv("data/inventory_stock.csv", header=True, inferSchema=True)
    tickets = spark.read.csv("data/support_tickets.csv", header=True, inferSchema=True)

    fact_sales = (
        orders.join(products.select("product_id", "unit_cost"), on="product_id")
        .withColumn("date_key", F.date_format("order_date", "yyyyMMdd").cast("int"))
        .withColumn("revenue", F.col("total_amount"))
        .withColumn("cogs", F.col("quantity") * F.col("unit_cost"))
        .withColumn("gross_margin", F.col("revenue") - F.col("cogs"))
        .select("order_id", "order_date", "date_key", "customer_id", "product_id",
                "quantity", "unit_price", "discount", "revenue", "cogs", "gross_margin",
                "payment_method", "channel", "order_status")
    )

    fact_inventory = (
        inventory
        .withColumn("date_key", F.date_format("snapshot_date", "yyyyMMdd").cast("int"))
        .withColumn("is_below_reorder", F.col("closing_stock") < F.col("reorder_level"))
    )

    fact_support = (
        tickets
        .withColumn("date_key", F.date_format("created_date", "yyyyMMdd").cast("int"))
        .withColumn("is_sla_breached", F.col("resolution_time_hours") > 48)
    )

    fact_sales.write.jdbc(JDBC_URL, "fact_sales", mode="append", properties=JDBC_PROPS)
    fact_inventory.write.jdbc(JDBC_URL, "fact_inventory", mode="append", properties=JDBC_PROPS)
    fact_support.write.jdbc(JDBC_URL, "fact_support_tickets", mode="append", properties=JDBC_PROPS)

    spark.stop()


if __name__ == "__main__":
    main()
