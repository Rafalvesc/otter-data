"""The no-Docker sample base: same data as PostgreSQL, without the personal column."""

from decimal import Decimal

import duckdb
import pytest

from backend.agents.analyst import AnalystService
from backend.config import Settings
from backend.sample.data import generate_dataset, reference_answers
from backend.sample.embedded import build_database, embedded_sample_runtime
from tests.helpers import ScriptedProvider, run


@pytest.fixture(scope="module")
def database(tmp_path_factory):
    return build_database(tmp_path_factory.mktemp("sample") / "sample.duckdb")


@pytest.fixture(scope="module")
def expected():
    return reference_answers(generate_dataset())


def scalar(database, sql):
    with duckdb.connect(str(database), read_only=True) as conn:
        return conn.execute(sql).fetchall()


def test_tables_match_the_analytics_views_without_email(database):
    tables = {row[0] for row in scalar(database, "SHOW TABLES")}
    assert tables == {"regions", "customers", "products", "orders", "order_items", "payments"}
    columns = [row[0] for row in scalar(database, "DESCRIBE customers")]
    assert columns == ["id", "region_id", "created_at"]


def test_reference_answers_hold_on_the_embedded_copy(database, expected):
    september = "completed_at >= '2026-09-01' AND completed_at < '2026-10-01'"
    revenue = scalar(
        database, f"SELECT SUM(amount) FROM payments WHERE status = 'completed' AND {september}"
    )[0][0]
    assert revenue == Decimal(expected["received_revenue"][0]["received_revenue"])
    customers = scalar(
        database,
        "SELECT COUNT(*) FROM customers WHERE created_at >= '2026-09-01' "
        "AND created_at < '2026-10-01'",
    )[0][0]
    assert customers == expected["new_customers"][0]["new_customers"]
    cancelled = scalar(
        database,
        "SELECT COUNT(*) FROM orders WHERE status = 'cancelled' "
        "AND cancelled_at >= '2026-09-01' AND cancelled_at < '2026-10-01'",
    )[0][0]
    assert cancelled == expected["cancelled_orders"][0]["cancelled_orders"]


def test_build_is_idempotent(database):
    before = database.stat().st_mtime_ns
    assert build_database(database) == database and database.stat().st_mtime_ns == before


def test_without_postgres_credentials_the_service_uses_the_embedded_sample(tmp_path):
    settings = Settings(
        _env_file=None, analytics_password=None, data_dir=str(tmp_path), llm_provider="ollama"
    )
    assert settings.embedded_sample
    analyst = AnalystService(settings, ScriptedProvider())
    sample = analyst.sample
    assert sample.id == "sample" and not sample.metrics_enabled and sample.kind == "sample"
    context = sample.context.explore_context()
    assert set(context["metrics"]) == {"received_revenue", "new_customers", "cancelled_orders"}
    assert "email" not in str(context["schema"])
    result = run(
        sample.executor.execute_async(
            "SELECT status, COUNT(id) AS n FROM main.orders GROUP BY status ORDER BY status"
        )
    )
    assert result.status == "success" and sum(row["n"] for row in result.rows) == 10000
    assert run(sample.executor.execute_async("SELECT email FROM main.customers")).status == "denied"


def test_runtime_reuses_the_file(tmp_path):
    settings = Settings(
        _env_file=None, analytics_password=None, data_dir=str(tmp_path), llm_provider="ollama"
    )
    embedded_sample_runtime(settings)
    files = sorted(path.name for path in tmp_path.iterdir())
    assert files == ["sample-ecommerce-v2.duckdb"]
    embedded_sample_runtime(settings)
    assert sorted(path.name for path in tmp_path.iterdir()) == files
