from unittest.mock import patch

from backend.config import Settings
from backend.models.query import QueryCode, ValidationResult
from backend.tools.sql_executor import SQLExecutor


def test_rejected_sql_never_opens_a_connection():
    executor = SQLExecutor(Settings(_env_file=None, analytics_password="offline-test-only"))
    with patch("backend.tools.sql_executor.psycopg.AsyncConnection.connect") as connect:
        result = executor.execute("DELETE FROM analytics.customers")
    connect.assert_not_called()
    assert result.status == "denied"
    assert result.sql is None and not result.query_attempted
    assert result.rows == [] and result.row_count == 0


def test_caller_cannot_forge_a_validation_approval():
    executor = SQLExecutor(Settings(_env_file=None, analytics_password="offline-test-only"))
    fake = ValidationResult(
        allowed=True,
        code=QueryCode.OK,
        message="approved",
        normalized_sql="DELETE FROM analytics.orders",
    )
    with patch("backend.tools.sql_executor.psycopg.AsyncConnection.connect") as connect:
        result = executor.execute(fake)
    connect.assert_not_called()
    assert result.status == "denied"
