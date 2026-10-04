import json
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from backend.sample.data import COLUMNS, generate_dataset, normalize
from scripts.golden_questions import QUESTIONS
from scripts.seed_database import connect_seed, seed_database

pytestmark = pytest.mark.integration


def test_analytics_role_and_read_only_defaults(analytics_connection):
    connection = analytics_connection
    assert connection.execute("SELECT current_user").fetchone()[0] == "analytics_agent"
    assert connection.execute("SHOW default_transaction_read_only").fetchone()[0] == "on"
    assert connection.execute("SHOW statement_timeout").fetchone()[0] == "10s"
    attributes = connection.execute(
        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
        "FROM pg_roles WHERE rolname = current_user"
    ).fetchone()
    assert attributes == (False, False, False, False, False)
    memberships = connection.execute(
        "SELECT COUNT(roleid) FROM pg_auth_members "
        "WHERE member = (SELECT oid FROM pg_roles WHERE rolname = current_user)"
    ).fetchone()[0]
    assert memberships == 0


@pytest.mark.parametrize("table", list(COLUMNS))
def test_allowed_views_match_seed_counts(analytics_connection, table):
    expected = len(generate_dataset()[table])
    # Identifiers come only from the constant test allowlist.
    result = analytics_connection.execute(
        psycopg.sql.SQL("SELECT COUNT(id) FROM {}").format(
            psycopg.sql.Identifier("analytics", table)
        )
    ).fetchone()[0]
    assert result == expected


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT email FROM core.customers",
        "SELECT id FROM core.orders",
        "SELECT email FROM analytics.customers",
    ],
)
def test_raw_or_sensitive_columns_are_unavailable(analytics_connection, statement):
    with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.UndefinedColumn)):
        analytics_connection.execute(statement)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE analytics.customers SET region_id = region_id WHERE id = 1",
        "DELETE FROM analytics.customers WHERE id = -1",
        "INSERT INTO analytics.customers (id, region_id, created_at) "
        "VALUES (-1, 1, TIMESTAMPTZ '2026-01-01 00:00:00-03')",
        "CREATE TABLE analytics.forbidden_test (id integer)",
        "CREATE TEMP TABLE forbidden_test (id integer)",
        "ALTER VIEW analytics.customers SET (security_barrier=false)",
        "SET ROLE seed_writer",
    ],
)
def test_privileges_block_writes_even_if_read_only_is_disabled(analytics_connection, statement):
    connection = analytics_connection
    connection.execute("SET default_transaction_read_only = off")
    # Rollback protects the fixture if an incorrectly configured grant lets a test write succeed.
    with connection.transaction():
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute(statement)


def test_database_statement_timeout(analytics_connection):
    analytics_connection.execute("SET statement_timeout = '100ms'")
    with pytest.raises(psycopg.errors.QueryCanceled):
        analytics_connection.execute("SELECT pg_sleep(1)")
    assert analytics_connection.execute("SELECT 1").fetchone() == (1,)


@pytest.mark.parametrize("question", QUESTIONS, ids=lambda question: question["id"])
def test_reference_sql_matches_independent_python_answers(analytics_connection, question):
    golden = json.loads(Path("evaluation/datasets/golden_questions.json").read_text("utf-8"))
    expected = next(row["expected"] for row in golden["questions"] if row["id"] == question["id"])
    with analytics_connection.cursor(row_factory=dict_row) as cursor:
        actual = cursor.execute(question["sql"], question["parameters"]).fetchall()
    assert normalize(actual) == expected


def test_repeated_seed_is_idempotent_and_does_not_write():
    with connect_seed() as connection:
        assert seed_database(connection) == "Dados já conferidos; nenhuma alteração realizada."
