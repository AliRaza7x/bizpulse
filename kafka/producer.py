import json
import os
import time

import pandas as pd
from dotenv import load_dotenv
from kafka import KafkaProducer

load_dotenv()

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9094")
TOPIC = "sales_orders"


def main():
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
    )
    orders = pd.read_csv("data/sales_orders.csv", parse_dates=["order_date"])

    for _, row in orders.iterrows():
        producer.send(TOPIC, value=row.to_dict())
        print(f"sent {row['order_id']}")
        time.sleep(0.2)

    producer.flush()
    producer.close()


if __name__ == "__main__":
    main()
