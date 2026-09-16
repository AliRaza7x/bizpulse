import argparse
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)
np.random.seed(42)

CATEGORIES = ["Apparel", "Footwear", "Accessories", "Home & Living", "Electronics", "Beauty"]
CHANNELS = ["Facebook", "Instagram", "Website", "WhatsApp", "Marketplace"]
PAYMENT_METHODS = ["COD", "Card", "JazzCash", "EasyPaisa", "Bank Transfer"]
ORDER_STATUS = ["Delivered", "Delivered", "Delivered", "Delivered", "Returned", "Cancelled", "Pending"]
PLATFORMS = ["Facebook Ads", "Instagram Ads", "Google Ads", "TikTok Ads"]
SEGMENTS = ["New", "Returning", "VIP"]
SUPPORT_CHANNELS = ["WhatsApp", "Facebook Messenger", "Email", "Phone", "Instagram DM"]
SUPPORT_CATEGORIES = ["Order Delay", "Product Defect", "Wrong Item", "Refund Request",
                       "General Inquiry", "Delivery Issue", "Payment Issue"]
PRIORITIES = ["Low", "Medium", "High", "Urgent"]
TICKET_STATUS = ["Resolved", "Resolved", "Resolved", "Open", "Escalated"]
CITIES = ["Karachi", "Lahore", "Islamabad", "Faisalabad", "Rawalpindi", "Multan", "Peshawar", "Hyderabad"]
PRODUCT_NOUNS = {
    "Apparel": ["Hoodie", "T-Shirt", "Kurta", "Jacket", "Trousers", "Shalwar Kameez", "Sweater"],
    "Footwear": ["Sneakers", "Sandals", "Loafers", "Boots", "Flip-Flops", "Formal Shoes"],
    "Accessories": ["Wallet", "Sunglasses", "Belt", "Watch", "Backpack", "Cap"],
    "Home & Living": ["Cushion Cover", "Table Lamp", "Bedsheet Set", "Wall Clock", "Storage Box"],
    "Electronics": ["Bluetooth Speaker", "Earbuds", "Power Bank", "Smart Watch", "Phone Case"],
    "Beauty": ["Face Serum", "Lipstick", "Perfume", "Face Wash", "Hair Oil"],
}
ADJECTIVES = ["Classic", "Premium", "Everyday", "Urban", "Signature", "Essential", "Deluxe", "Original"]


def daterange(start, days):
    return [start + timedelta(days=i) for i in range(days)]


def gen_customers(n):
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "customer_id": f"CUST{i:05d}",
            "name": fake.name(),
            "email": fake.unique.email(),
            "city": random.choice(CITIES),
            "country": "Pakistan",
            "signup_date": fake.date_between(start_date="-2y", end_date="-1d"),
            "customer_segment": random.choices(SEGMENTS, weights=[0.5, 0.4, 0.1])[0],
        })
    return pd.DataFrame(rows)


def gen_products(n):
    rows = []
    for i in range(1, n + 1):
        cost = round(random.uniform(300, 4000), 2)
        margin = random.uniform(1.3, 2.5)
        category = random.choice(CATEGORIES)
        rows.append({
            "product_id": f"PROD{i:04d}",
            "product_name": f"{random.choice(ADJECTIVES)} {random.choice(PRODUCT_NOUNS[category])}",
            "category": category,
            "unit_cost": cost,
            "unit_price": round(cost * margin, 2),
        })
    return pd.DataFrame(rows)


def gen_campaigns(n, start_date, total_days):
    rows = []
    for i in range(1, n + 1):
        c_start = start_date + timedelta(days=random.randint(0, max(total_days - 14, 0)))
        c_end = c_start + timedelta(days=random.randint(7, 30))
        rows.append({
            "campaign_id": f"CMP{i:03d}",
            "campaign_name": f"{random.choice(['Summer','Eid','Winter','Flash','Clearance','New Arrivals'])} {random.choice(CATEGORIES)} Push",
            "platform": random.choice(PLATFORMS),
            "start_date": c_start.date(),
            "end_date": c_end.date(),
            "budget": round(random.uniform(5000, 150000), 2),
            "objective": random.choice(["Conversions", "Traffic", "Brand Awareness", "Engagement"]),
            "target_segment": random.choice(SEGMENTS),
        })
    return pd.DataFrame(rows)


def gen_sales_orders(n, customers, products, start_date, total_days):
    rows = []
    cust_ids = customers["customer_id"].tolist()
    prod = products.set_index("product_id")
    prod_ids = prod.index.tolist()
    for i in range(1, n + 1):
        pid = random.choice(prod_ids)
        price = float(prod.loc[pid, "unit_price"])
        qty = random.choices([1, 2, 3, 4], weights=[0.6, 0.25, 0.1, 0.05])[0]
        discount = round(random.choices([0, 0, 0, 0.05, 0.1, 0.15], weights=[0.5,0.15,0.1,0.1,0.1,0.05])[0] * price * qty, 2)
        order_date = start_date + timedelta(days=random.randint(0, total_days - 1),
                                             hours=random.randint(8, 22), minutes=random.randint(0, 59))
        rows.append({
            "order_id": f"ORD{i:06d}",
            "order_date": order_date,
            "customer_id": random.choice(cust_ids),
            "product_id": pid,
            "quantity": qty,
            "unit_price": price,
            "discount": discount,
            "total_amount": round(price * qty - discount, 2),
            "payment_method": random.choice(PAYMENT_METHODS),
            "channel": random.choice(CHANNELS),
            "order_status": random.choice(ORDER_STATUS),
        })
    return pd.DataFrame(rows).sort_values("order_date").reset_index(drop=True)


def gen_inventory_stock(products, start_date, total_days):
    rows = []
    stock_level = {pid: random.randint(80, 400) for pid in products["product_id"]}
    reorder = {pid: random.randint(20, 60) for pid in products["product_id"]}
    for d in daterange(start_date, total_days):
        for pid in products["product_id"]:
            stock_in = random.choice([0, 0, 0, 0, 20, 50, 100]) if random.random() < 0.15 else 0
            stock_out = max(0, int(np.random.poisson(3)))
            stock_level[pid] = max(0, stock_level[pid] + stock_in - stock_out)
            rows.append({
                "snapshot_date": d.date(),
                "product_id": pid,
                "warehouse_location": random.choice(["Karachi-Main", "Lahore-Hub"]),
                "stock_in": stock_in,
                "stock_out": stock_out,
                "closing_stock": stock_level[pid],
                "reorder_level": reorder[pid],
            })
    return pd.DataFrame(rows)


def gen_marketing_daily_spend(campaigns, start_date, total_days):
    rows = []
    for _, c in campaigns.iterrows():
        c_start = pd.to_datetime(c["start_date"])
        c_end = pd.to_datetime(c["end_date"])
        active_days = max((c_end - c_start).days, 1)
        daily_budget = c["budget"] / active_days
        for d in pd.date_range(c_start, c_end):
            impressions = max(int(np.random.normal(8000, 2000)), 200)
            clicks = int(impressions * random.uniform(0.01, 0.05))
            spend = round(daily_budget * random.uniform(0.7, 1.3), 2)
            leads = int(clicks * random.uniform(0.05, 0.2))
            conversions = int(leads * random.uniform(0.1, 0.4))
            rows.append({
                "date": d.date(),
                "campaign_id": c["campaign_id"],
                "platform": c["platform"],
                "impressions": impressions,
                "clicks": clicks,
                "spend": spend,
                "leads_generated": leads,
                "conversions": conversions,
            })
    return pd.DataFrame(rows)


def gen_support_tickets(n, customers, sales_orders, start_date, total_days):
    rows = []
    cust_ids = customers["customer_id"].tolist()
    order_ids = sales_orders["order_id"].tolist()
    for i in range(1, n + 1):
        created = start_date + timedelta(days=random.randint(0, total_days - 1), hours=random.randint(8, 22))
        status = random.choice(TICKET_STATUS)
        resolution_time = round(random.uniform(0.5, 72), 1) if status != "Open" else None
        rows.append({
            "ticket_id": f"TCK{i:05d}",
            "customer_id": random.choice(cust_ids),
            "created_date": created,
            "channel": random.choice(SUPPORT_CHANNELS),
            "category": random.choice(SUPPORT_CATEGORIES),
            "priority": random.choices(PRIORITIES, weights=[0.4, 0.35, 0.2, 0.05])[0],
            "status": status,
            "resolution_time_hours": resolution_time,
            "satisfaction_rating": random.choice([1, 2, 3, 4, 5, 4, 5, None]) if status == "Resolved" else None,
            "related_order_id": random.choice(order_ids) if random.random() < 0.6 else None,
        })
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--customers", type=int, default=300)
    ap.add_argument("--products", type=int, default=60)
    ap.add_argument("--campaigns", type=int, default=25)
    ap.add_argument("--orders", type=int, default=1500)
    ap.add_argument("--tickets", type=int, default=450)
    ap.add_argument("--days", type=int, default=120)
    args = ap.parse_args()

    start_date = datetime.now() - timedelta(days=args.days)

    customers = gen_customers(args.customers)
    products = gen_products(args.products)
    campaigns = gen_campaigns(args.campaigns, start_date, args.days)
    daily_spend = gen_marketing_daily_spend(campaigns, start_date, args.days)
    sales_orders = gen_sales_orders(args.orders, customers, products, start_date, args.days)
    inventory = gen_inventory_stock(products, start_date, args.days)
    tickets = gen_support_tickets(args.tickets, customers, sales_orders, start_date, args.days)

    frames = {
        "customers.csv": customers, "products.csv": products,
        "sales_orders.csv": sales_orders, "inventory_stock.csv": inventory,
        "marketing_campaigns.csv": campaigns, "marketing_daily_spend.csv": daily_spend,
        "support_tickets.csv": tickets,
    }
    for fname, df in frames.items():
        df.to_csv(f"data/{fname}", index=False)
        print(f"wrote data/{fname}  ({len(df):,} rows)")


if __name__ == "__main__":
    main()
