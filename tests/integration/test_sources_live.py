"""Connected sources against real servers.

PostgreSQL uses the local Docker database. MySQL runs only when OTTER_TEST_MYSQL_* variables
point to a server with a `shop` database
(throwaway container: docs/historico-de-validacao.md).
"""

import os

import pytest
from dotenv import load_dotenv
from pydantic import SecretStr

from backend.config import Settings
from backend.models.query import QueryCode
from backend.sources.engines import Connection, SourceError, run_query
from backend.sources.models import DatabaseSourceInput
from backend.sources.registry import RegistryError, SourceRegistry
from tests.helpers import run
from tests.unit.test_sources import MemorySecrets

pytestmark = pytest.mark.integration


def postgres(user: str, password: str) -> Connection:
    load_dotenv()
    return Connection(
        kind="postgres",
        host=os.getenv("DATABASE_HOST", "127.0.0.1"),
        port=int(os.getenv("DATABASE_PORT", "55432")),
        database=os.getenv("DATABASE_NAME", "datapilot"),
        user=user,
        password=password,
    )


def registry(tmp_path, **settings):
    return SourceRegistry(
        Settings(_env_file=None, analytics_password="x", **settings),
        secrets=MemorySecrets(),
        data_dir=tmp_path,
    )


def test_postgres_source_discovers_views_and_answers_with_known_values(tmp_path):
    load_dotenv()
    reg = registry(tmp_path)
    summary = reg.add_database(
        DatabaseSourceInput(
            name="Loja",
            kind="postgres",
            host=os.getenv("DATABASE_HOST", "127.0.0.1"),
            port=int(os.getenv("DATABASE_PORT", "55432")),
            database=os.getenv("DATABASE_NAME", "datapilot"),
            user="analytics_agent",
            password=SecretStr(os.environ["ANALYTICS_PASSWORD"]),
            schema_name="analytics",
        )
    )
    assert summary.tables == 6
    catalog = reg.detail(summary.id).catalog
    assert catalog["customers"].relationships == {"region_id": "regions.id"}
    result = run(
        reg.runtime(summary.id).executor.execute_async(
            "SELECT r.name AS region, COUNT(c.id) AS n FROM analytics.customers c "
            "JOIN analytics.regions r ON c.region_id = r.id GROUP BY r.name ORDER BY n DESC, region"
        )
    )
    assert result.status == "success"
    assert sum(row["n"] for row in result.rows) == 1000 and result.rows[0]["region"] == "Northeast"


def test_postgres_wrong_password_gives_a_clean_message(tmp_path):
    with pytest.raises(RegistryError) as error:
        registry(tmp_path).add_database(
            DatabaseSourceInput(
                name="x",
                kind="postgres",
                host="127.0.0.1",
                port=int(os.getenv("DATABASE_PORT", "55432")),
                database="datapilot",
                user="analytics_agent",
                password=SecretStr("wrong-password"),
            )
        )
    assert "confira host, porta, usuário e senha" in error.value.message
    assert "wrong-password" not in error.value.message


def test_postgres_session_is_read_only_even_for_an_account_that_can_write():
    # seed_writer may INSERT into core; the source session must still refuse it.
    load_dotenv()
    connection = postgres("seed_writer", os.environ["SEED_PASSWORD"])
    with pytest.raises(SourceError) as error:
        run_query(
            connection,
            "INSERT INTO core.regions (id, name, state) VALUES (99, 'Teste', 'TT')",
            (),
            timeout=5,
            max_rows=10,
            max_bytes=10_000,
        )
    assert error.value.code == QueryCode.EXECUTION_ERROR


def test_postgres_session_has_a_statement_timeout():
    load_dotenv()
    connection = postgres("analytics_agent", os.environ["ANALYTICS_PASSWORD"])
    with pytest.raises(SourceError) as error:
        run_query(connection, "SELECT pg_sleep(5)", (), timeout=1, max_rows=10, max_bytes=10_000)
    assert error.value.code == QueryCode.TIMEOUT


MYSQL = {
    key: os.getenv(f"OTTER_TEST_MYSQL_{key.upper()}")
    for key in ("host", "port", "user", "password")
}
needs_mysql = pytest.mark.skipif(
    not all(MYSQL.values()), reason="Defina OTTER_TEST_MYSQL_* para testar MySQL."
)


def mysql_connection() -> Connection:
    return Connection(
        kind="mysql",
        host=MYSQL["host"],
        port=int(MYSQL["port"]),
        database="shop",
        user=MYSQL["user"],
        password=MYSQL["password"],
    )


@needs_mysql
def test_mysql_source_discovers_keys_hides_email_and_binds_parameters(tmp_path):
    reg = registry(tmp_path)
    summary = reg.add_database(
        DatabaseSourceInput(
            name="Loja MySQL",
            kind="mysql",
            host=MYSQL["host"],
            port=int(MYSQL["port"]),
            database="shop",
            user=MYSQL["user"],
            password=SecretStr(MYSQL["password"]),
        )
    )
    catalog = reg.detail(summary.id).catalog
    assert catalog["orders"].relationships == {
        "customer_id": "customers.id",
        "product_id": "products.id",
    }
    assert catalog["customers"].hidden_columns == ["email"]
    result = run(
        reg.runtime(summary.id).executor.execute_async(
            "SELECT DATE_FORMAT(o.ordered_at, '%Y-%m-01') AS mes, "
            "SUM(o.quantity * p.price) AS receita "
            "FROM shop.orders o JOIN shop.products p ON o.product_id = p.id "
            "WHERE o.ordered_at >= :inicio AND (o.note LIKE '%ok%' OR o.note IS NULL) "
            "GROUP BY 1 ORDER BY 1",
            {"inicio": "2026-01-01"},
        )
    )
    assert result.status == "success"
    assert [row["receita"] for row in result.rows] == ["71.00", "240.00", "395.50"]


@needs_mysql
def test_mysql_session_blocks_writes_and_slow_statements():
    with pytest.raises(SourceError) as write:
        run_query(
            mysql_connection(),
            "UPDATE shop.products SET price = 0",
            (),
            timeout=5,
            max_rows=10,
            max_bytes=10_000,
        )
    assert write.value.code == QueryCode.EXECUTION_ERROR
    with pytest.raises(SourceError) as slow:
        run_query(
            mysql_connection(),
            "SELECT SLEEP(5) AS s FROM shop.products",
            (),
            timeout=1,
            max_rows=10,
            max_bytes=10_000,
        )
    assert slow.value.code == QueryCode.TIMEOUT
