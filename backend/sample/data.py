"""Deterministic synthetic ecommerce data; no database or model needed."""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from random import Random
from typing import Any

SEED = 42
DATASET_VERSION = "ecommerce-v2"  # v2: names in English; same values as v1
LOCAL_TZ = timezone(timedelta(hours=-3))
START = datetime(2026, 1, 1, tzinfo=LOCAL_TZ)
END = datetime(2026, 9, 28, tzinfo=LOCAL_TZ)
PERIOD_START = datetime(2026, 9, 1, tzinfo=LOCAL_TZ)
PERIOD_END = datetime(2026, 10, 1, tzinfo=LOCAL_TZ)
REFERENCE_DATE = date(2026, 9, 30)
# Brazilian macro-regions (English names), each with a representative state.
REGIONS = (
    ("South", "RS"),
    ("Southeast", "SP"),
    ("Northeast", "BA"),
    ("North", "AM"),
    ("Central-West", "GO"),
)
REGION_NAMES = frozenset(name for name, _ in REGIONS)

COLUMNS = {
    "regions": ("id", "name", "state"),
    "customers": ("id", "region_id", "created_at", "email"),
    "products": ("id", "name", "category", "current_price"),
    "orders": ("id", "customer_id", "ordered_at", "status", "cancelled_at"),
    "order_items": ("id", "order_id", "product_id", "quantity", "unit_price"),
    "payments": ("id", "order_id", "amount", "status", "completed_at"),
}


def normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    return value


def generate_dataset() -> dict[str, list[dict[str, Any]]]:
    rng = Random(SEED)
    data: dict[str, list[dict[str, Any]]] = {table: [] for table in COLUMNS}
    for identifier, (name, state) in enumerate(REGIONS, start=1):
        data["regions"].append({"id": identifier, "name": name, "state": state})

    customer_start = datetime(2025, 10, 1, tzinfo=LOCAL_TZ)
    for identifier in range(1, 1001):
        created_at = customer_start + timedelta(
            seconds=rng.randrange(int((END - customer_start).total_seconds()))
        )
        data["customers"].append(
            {
                "id": identifier,
                "region_id": rng.randint(1, 5),
                "created_at": created_at,
                "email": f"synthetic-{identifier}@example.invalid",
            }
        )

    categories = ("Electronics", "Home", "Sports", "Books", "Accessories")
    for identifier in range(1, 101):
        data["products"].append(
            {
                "id": identifier,
                "name": f"Product {identifier:03d}",
                "category": categories[(identifier - 1) % len(categories)],
                "current_price": Decimal(rng.randint(1500, 90000)) / 100,
            }
        )

    item_id = 0
    for identifier in range(1, 10001):
        customer = rng.choice(data["customers"])
        earliest = max(START, customer["created_at"])
        ordered_at = earliest + timedelta(
            seconds=rng.randrange(int((END - earliest).total_seconds()))
        )
        status = rng.choices(("paid", "cancelled", "pending"), weights=(82, 12, 6))[0]
        settled_at = ordered_at + timedelta(hours=rng.randint(1, 36))
        data["orders"].append(
            {
                "id": identifier,
                "customer_id": customer["id"],
                "ordered_at": ordered_at,
                "status": status,
                "cancelled_at": settled_at if status == "cancelled" else None,
            }
        )
        total = Decimal("0.00")
        for product in rng.sample(data["products"], rng.randint(1, 4)):
            item_id += 1
            quantity = rng.randint(1, 3)
            # Price is a historical snapshot; current product prices are not revenue.
            unit_price = product["current_price"]
            total += quantity * unit_price
            data["order_items"].append(
                {
                    "id": item_id,
                    "order_id": identifier,
                    "product_id": product["id"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                }
            )
        payment_status = {"paid": "completed", "cancelled": "failed", "pending": "pending"}
        data["payments"].append(
            {
                "id": identifier,
                "order_id": identifier,
                "amount": total,
                "status": payment_status[status],
                "completed_at": settled_at if status == "paid" else None,
            }
        )
    return data


def fingerprint(data: dict[str, list[dict[str, Any]]]) -> str:
    encoded = json.dumps(normalize(data), sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def reference_answers(data: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Independent Python ground truth; this does not execute the reference SQL."""
    customers = {row["id"]: row for row in data["customers"]}
    orders = {row["id"]: row for row in data["orders"]}
    regions = {row["id"]: row for row in data["regions"]}
    by_region: dict[str, Decimal] = {}
    by_month: dict[str, Decimal] = {}
    revenue = Decimal("0.00")
    for payment in data["payments"]:
        if payment["status"] != "completed":
            continue
        completed_at = payment["completed_at"]
        if START <= completed_at < PERIOD_END:
            month = completed_at.date().replace(day=1).isoformat()
            by_month[month] = by_month.get(month, Decimal("0.00")) + payment["amount"]
        if PERIOD_START <= completed_at < PERIOD_END:
            revenue += payment["amount"]
            customer = customers[orders[payment["order_id"]]["customer_id"]]
            region = regions[customer["region_id"]]["name"]
            by_region[region] = by_region.get(region, Decimal("0.00")) + payment["amount"]
    return normalize(
        {
            "new_customers": [
                {
                    "new_customers": sum(
                        PERIOD_START <= row["created_at"] < PERIOD_END for row in customers.values()
                    )
                }
            ],
            "received_revenue": [{"received_revenue": revenue}],
            "revenue_by_region": [
                {"region": name, "received_revenue": amount}
                for name, amount in sorted(by_region.items(), key=lambda item: (-item[1], item[0]))
            ],
            "monthly_revenue": [
                {"month": month, "received_revenue": amount}
                for month, amount in sorted(by_month.items())
            ],
            "cancelled_orders": [
                {
                    "cancelled_orders": sum(
                        row["status"] == "cancelled"
                        and PERIOD_START <= row["cancelled_at"] < PERIOD_END
                        for row in orders.values()
                    )
                }
            ],
        }
    )
