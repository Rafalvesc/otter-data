import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from backend.sample.data import COLUMNS, generate_dataset, normalize, reference_answers
from scripts.export_golden import build_golden


@pytest.fixture(scope="module")
def dataset():
    return generate_dataset()


def test_golden_fixture_is_reproducible():
    committed = json.loads(Path("evaluation/datasets/golden_questions.json").read_text("utf-8"))
    assert build_golden() == committed


def test_foreign_keys_and_event_order(dataset):
    customers = {row["id"]: row for row in dataset["customers"]}
    orders = {row["id"]: row for row in dataset["orders"]}
    regions = {row["id"] for row in dataset["regions"]}
    products = {row["id"] for row in dataset["products"]}
    for customer in customers.values():
        assert customer["region_id"] in regions
        assert customer["email"].endswith("@example.invalid")
    for order in orders.values():
        assert order["ordered_at"] >= customers[order["customer_id"]]["created_at"]
        assert (order["status"] == "cancelled") == (order["cancelled_at"] is not None)
        if order["cancelled_at"]:
            assert order["cancelled_at"] >= order["ordered_at"]
    for item in dataset["order_items"]:
        assert item["order_id"] in orders and item["product_id"] in products
        assert item["quantity"] > 0 and item["unit_price"] > 0
    for payment in dataset["payments"]:
        order = orders[payment["order_id"]]
        assert (payment["status"] == "completed") == (payment["completed_at"] is not None)
        if payment["completed_at"]:
            assert payment["completed_at"] >= order["ordered_at"]


def test_payment_amount_matches_items_and_reference_aggregates(dataset):
    totals = defaultdict(lambda: Decimal("0.00"))
    for item in dataset["order_items"]:
        totals[item["order_id"]] += item["quantity"] * item["unit_price"]
    assert len(totals) == 10000
    for payment in dataset["payments"]:
        assert payment["amount"] == totals[payment["order_id"]]
    answers = reference_answers(dataset)
    revenue = Decimal(answers["received_revenue"][0]["received_revenue"])
    assert revenue > 0
    assert revenue == sum(Decimal(row["received_revenue"]) for row in answers["revenue_by_region"])
    assert len(answers["monthly_revenue"]) == 9
    assert all(Decimal(row["received_revenue"]) > 0 for row in answers["monthly_revenue"])


def test_semantic_catalog_matches_allowed_columns(dataset):
    schema = yaml.safe_load(Path("backend/semantic/schema.yaml").read_text("utf-8"))
    metrics = yaml.safe_load(Path("backend/semantic/metrics.yaml").read_text("utf-8"))
    assert schema["schema"] == "analytics"
    assert set(schema["tables"]) == set(COLUMNS)
    for table, spec in schema["tables"].items():
        expected = set(dataset[table][0]) - {"email"}
        assert set(spec["columns"]) == expected
        for relation in spec.get("relationships", {}).values():
            target, column = relation.split(".")
            assert column in schema["tables"][target]["columns"]
    for metric in metrics["metrics"].values():
        table = metric["source"].split(".")[1]
        assert metric["date_column"] in schema["tables"][table]["columns"]
    assert normalize(Decimal("12.30")) == "12.30"
