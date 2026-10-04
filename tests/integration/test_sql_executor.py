import json
from pathlib import Path

import pytest

from backend.config import Settings
from backend.models.query import QueryCode
from backend.tools.sql_executor import SQLExecutor
from scripts.golden_questions import QUESTIONS

pytestmark = pytest.mark.integration


@pytest.fixture
def executor():
    return SQLExecutor(Settings())


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda item: item["id"])
def test_validated_executor_matches_golden_answers(executor, question):
    sql = question["sql"].replace("%s", ":start_date", 1).replace("%s", ":end_date", 1)
    result = executor.execute(
        sql, dict(zip(("start_date", "end_date"), question["parameters"], strict=True))
    )
    golden = json.loads(Path("evaluation/datasets/golden_questions.json").read_text("utf-8"))
    expected = next(row["expected"] for row in golden["questions"] if row["id"] == question["id"])
    assert result.status == "success", result
    assert result.rows == expected
    assert result.query_attempted and not result.truncated
    assert "LIMIT 10001" in result.sql
    assert result.duration_ms > 0 and result.sources


def test_limits_are_enforced_and_truncation_is_explicit():
    executor = SQLExecutor(Settings(max_rows=3))
    result = executor.execute("SELECT id FROM analytics.customers ORDER BY id")
    assert result.status == "success"
    assert result.rows == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert result.truncated and result.truncation_reason == "row_limit"
    assert "LIMIT 4" in result.sql
    exact = executor.execute("SELECT id FROM analytics.customers ORDER BY id LIMIT 3")
    assert exact.status == "success" and not exact.truncated


def test_byte_budget_counts_utf8_and_json_delimiters():
    executor = SQLExecutor(Settings(max_result_bytes=128))
    result = executor.execute("SELECT name FROM analytics.products ORDER BY id")
    assert result.status == "success" and result.truncation_reason == "byte_limit"
    assert result.result_bytes <= 128
    assert result.result_bytes == len(
        json.dumps(result.rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    assert result.row_count < 100


def test_parameters_and_percent_literals_are_not_interpolated(executor):
    result = executor.execute(
        "SELECT id FROM analytics.orders WHERE status = :status",
        {"status": "paid'; DELETE FROM analytics.orders; --"},
    )
    assert result.status == "success" and result.row_count == 0
    assert "DELETE" not in result.sql
    like = executor.execute(
        "SELECT name FROM analytics.products WHERE name LIKE 'Product %' AND id = :id",
        {"id": 1},
    )
    assert like.status == "success" and like.rows == [{"name": "Product 001"}]


def test_empty_results_and_precision_are_preserved(executor):
    empty = executor.execute("SELECT id FROM analytics.customers WHERE id = -1")
    assert empty.status == "success" and empty.rows == [] and not empty.truncated
    precise = executor.execute(
        "SELECT CAST(1.2345 AS numeric(10,4)) AS value FROM analytics.orders LIMIT 1"
    )
    assert precise.status == "success" and precise.rows == [{"value": "1.2345"}]


def test_database_errors_are_sanitized_and_do_not_break_next_request(executor, caplog):
    caplog.set_level("INFO", logger="backend.tools.sql_executor")
    result = executor.execute(
        "SELECT CAST(:value AS integer) AS value FROM analytics.orders LIMIT 1",
        {"value": "private-secret-marker"},
    )
    assert result.status == "error" and result.code == QueryCode.EXECUTION_ERROR
    assert not result.rows and "private-secret-marker" not in result.model_dump_json()
    assert "private-secret-marker" not in caplog.text
    assert caplog.records[0].query_code == QueryCode.EXECUTION_ERROR.value
    assert executor.execute("SELECT id FROM analytics.orders LIMIT 1").status == "success"


def test_timeout_uses_real_blocked_query_and_recovers():
    # The admin test connection holds a temporary lock, without changing rows or grants.
    import os

    import psycopg
    from dotenv import load_dotenv

    load_dotenv()
    with psycopg.connect(
        host=os.getenv("DATABASE_HOST", "127.0.0.1"),
        port=int(os.getenv("DATABASE_PORT", "55432")),
        dbname=os.getenv("DATABASE_NAME", "datapilot"),
        user=os.getenv("POSTGRES_USER", "datapilot_admin"),
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    ) as blocking:
        with blocking.transaction():
            blocking.execute("LOCK TABLE core.orders IN ACCESS EXCLUSIVE MODE")
            result = SQLExecutor(Settings(query_timeout_seconds=1)).execute(
                "SELECT id FROM analytics.orders LIMIT 1"
            )
            assert result.status == "error" and result.code == QueryCode.TIMEOUT
            assert result.duration_ms < 5000
            assert result.rows == []
    assert (
        SQLExecutor(Settings()).execute("SELECT id FROM analytics.orders LIMIT 1").status
        == "success"
    )


def test_connection_failure_is_sanitized():
    result = SQLExecutor(Settings(database_port=1)).execute(
        "SELECT id FROM analytics.orders LIMIT 1"
    )
    assert result.status == "error" and result.code == QueryCode.CONNECTION_ERROR
    assert not result.query_attempted and result.sql is None


def test_postgres_errors_carry_only_a_fixed_hint(executor):
    division = executor.execute("SELECT 1 / (COUNT(id) - COUNT(id)) AS ratio FROM analytics.orders")
    assert division.status == "error" and division.code == QueryCode.EXECUTION_ERROR
    assert division.retry_hint and "NULLIF" in division.retry_hint
    rounded = executor.execute("SELECT ROUND(CORR(amount, id), 3) AS r FROM analytics.payments")
    assert rounded.status == "success", rounded.message
