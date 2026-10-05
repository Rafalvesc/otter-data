"""MongoDB sources: a read-only snapshot in DuckDB, queried with the same validated SQL."""

import datetime as dt
from decimal import Decimal

import pytest
from bson import Decimal128, ObjectId
from pydantic import SecretStr, ValidationError
from pymongo import errors

from backend.models.query import QueryCode
from backend.sources import mongo
from backend.sources.models import DatabaseSourceInput
from backend.sources.registry import RegistryError, SourceRegistry
from tests.helpers import run
from tests.unit.test_sources import MemorySecrets, settings

ADA, BOB = ObjectId(), ObjectId()
ORDER_1, ORDER_2 = ObjectId(), ObjectId()


def store():
    return {
        "customers": [
            {"_id": ADA, "name": "Ada", "email": "ada@x.com", "address": {"city": "Recife"}},
            {"_id": BOB, "name": "Bob", "email": "bob@x.com", "address": {"city": "Natal"}},
        ],
        "orders": [
            {
                "_id": ORDER_1,
                "customer_id": str(ADA),
                "created_at": dt.datetime(2026, 9, 3, 12, 30),
                "total": Decimal128("30.00"),
                "items": [
                    {"sku": "A", "qty": 1, "price": 10.0},
                    {"sku": "B", "qty": 2, "price": 10.0},
                ],
                "tags": ["gift", "promo"],
            },
            {
                "_id": ORDER_2,
                "customer_id": str(BOB),
                "created_at": dt.datetime(2026, 9, 5),
                "total": Decimal128("5.50"),
                "items": [{"sku": "A", "qty": 1, "price": 5.5}],
                "tags": [],
            },
        ],
        "empty": [],
        "system.views": [{"_id": 1}],
    }


class Cursor:
    def __init__(self, documents):
        self.documents = documents

    def limit(self, count):
        return Cursor(self.documents[:count])

    def __iter__(self):
        return iter(self.documents)


class Collection:
    def __init__(self, documents):
        self.documents = documents

    def find(self, query, **options):
        assert query == {} and options["max_time_ms"] > 0
        return Cursor(self.documents)


class Database:
    def __init__(self, data):
        self.data = data

    def list_collection_names(self):
        return list(self.data)

    def __getitem__(self, name):
        return Collection(self.data[name])


class Client:
    """Only what the import uses: ping, list_collection_names and find."""

    def __init__(self, data, fail):
        self.data, self.fail = data, fail
        self.admin = self

    def command(self, name):
        if self.fail:
            raise self.fail
        assert name == "ping"

    def __getitem__(self, database):
        return Database(self.data)

    def close(self):
        pass


class Server:
    """Stands in for pymongo.MongoClient, recording how it was called."""

    def __init__(self):
        self.data = store()
        self.fail = None
        self.calls = []

    def connect(self, connection, auth_source, timeout):
        self.calls.append((connection, auth_source))
        return Client(self.data, self.fail)


@pytest.fixture
def server(monkeypatch):
    fake = Server()
    monkeypatch.setattr(mongo, "connect", fake.connect)
    return fake


@pytest.fixture
def registry(tmp_path):
    return SourceRegistry(settings(), secrets=MemorySecrets(), data_dir=tmp_path / "data")


def source_input(**updates):
    values = dict(
        name="Loja (Mongo)",
        kind="mongodb",
        host="mongo.local",
        port=27017,
        database="loja-prod",
        user="reader",
        password=SecretStr("mongo-secret"),
    )
    return DatabaseSourceInput(**(values | updates))


def test_documents_are_flattened_like_the_bi_connector():
    row, children = mongo.flatten(store()["orders"][0])
    assert row["id"] == str(ORDER_1) and row["customer_id"] == str(ADA)
    assert row["created_at"] == "2026-09-03 12:30:00" and row["total"] == 30.0
    assert row["tags"] == '["gift", "promo"]'
    assert list(children) == ["items"] and len(children["items"]) == 2
    deep, _ = mongo.flatten({"a": {"b": {"c": {"d": 1}}}, "Valor Total": Decimal("2.5")})
    assert deep == {"a_b_c": '{"d": 1}', "valor_total": 2.5}


def test_collections_become_tables_with_child_tables_and_hidden_personal_fields(server, registry):
    summary = registry.add_database(source_input())
    assert summary.kind == "mongodb" and summary.location == "reader@mongo.local:27017/loja-prod"
    connection, auth_source = server.calls[0]
    assert auth_source == "admin" and connection.password == "mongo-secret"
    detail = registry.detail(summary.id)
    assert set(detail.catalog) == {"customers", "orders", "orders_items"}  # no empty, no system.*
    customers = detail.catalog["customers"]
    assert "email" not in customers.columns and "email" in customers.hidden_columns
    assert detail.catalog["orders"].relationships == {"customer_id": "customers.id"}
    assert detail.catalog["orders_items"].relationships == {"orders_id": "orders.id"}
    assert registry._secrets.get(summary.id) == "mongo-secret"  # vault, not the config file
    assert "mongo-secret" not in (registry.root / "sources.json").read_text(encoding="utf-8")


def test_questions_run_as_validated_sql_on_the_copy(server, registry):
    runtime = registry.runtime(registry.add_database(source_input()).id)
    revenue = run(
        runtime.executor.execute_async(
            "SELECT o.customer_id, SUM(i.qty * i.price) AS revenue FROM main.orders_items AS i "
            "JOIN main.orders AS o ON i.orders_id = o.id GROUP BY o.customer_id "
            "ORDER BY revenue DESC"
        )
    )
    assert revenue.status == "success"
    assert [row["revenue"] for row in revenue.rows] == [30.0, 5.5]
    # The order total summed once per item would be inflated: refused before running.
    inflated = run(
        runtime.executor.execute_async(
            "SELECT SUM(o.total) AS total FROM main.orders AS o "
            "JOIN main.orders_items AS i ON i.orders_id = o.id"
        )
    )
    assert inflated.status == "denied" and inflated.code == QueryCode.DUPLICATED_AGGREGATE
    hidden = run(runtime.executor.execute_async("SELECT email FROM main.customers"))
    assert hidden.status == "denied"


def test_refresh_reimports_and_a_failed_refresh_keeps_the_previous_copy(server, registry):
    source = registry.add_database(source_input())
    server.data["orders"].append({"_id": ObjectId(), "customer_id": str(ADA), "items": []})
    assert registry.refresh(source.id).tables == 3
    rows = run(
        registry.runtime(source.id).executor.execute_async("SELECT COUNT(id) AS n FROM main.orders")
    ).rows
    assert rows == [{"n": 3}]
    server.fail = errors.ServerSelectionTimeoutError("down")
    with pytest.raises(RegistryError, match="Não foi possível conectar ao MongoDB"):
        registry.refresh(source.id)
    rows = run(
        registry.runtime(source.id).executor.execute_async("SELECT COUNT(id) AS n FROM main.orders")
    ).rows
    assert rows == [{"n": 3}]


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (errors.OperationFailure("auth failed"), "O MongoDB recusou o acesso"),
        (errors.ServerSelectionTimeoutError("no server"), "Não foi possível conectar ao MongoDB"),
    ],
)
def test_connection_errors_use_fixed_messages_and_leave_no_files(
    server, registry, failure, message
):
    server.fail = failure
    with pytest.raises(RegistryError, match=message) as raised:
        registry.add_database(source_input())
    assert "auth failed" not in str(raised.value) and "no server" not in str(raised.value)
    assert registry.configs() == []
    assert not list((registry.root / "sources").glob("*.duckdb"))


def test_large_collections_are_capped_and_the_cap_is_reported(server, registry, monkeypatch):
    monkeypatch.setattr(mongo, "MAX_DOCUMENTS", 1)
    detail = registry.detail(registry.add_database(source_input()).id)
    assert "coleção orders: importados os primeiros 1 documentos" in detail.skipped


def test_a_server_without_authentication_needs_no_password(server, registry):
    summary = registry.add_database(source_input(user="", password=SecretStr(""), schema_name=None))
    assert summary.location == "mongo.local:27017/loja-prod"
    assert registry._secrets.get(summary.id) is None
    registry.refresh(summary.id)  # no vault lookup for a passwordless server


def test_sql_databases_still_require_a_user_and_a_plain_database_name():
    with pytest.raises(ValidationError):
        source_input(kind="postgres", user="")
    with pytest.raises(ValidationError):
        source_input(kind="mysql", database="loja-prod")
    with pytest.raises(ValidationError):
        source_input(kind="postgres", schema_name="sales-2026")
    mongodb = source_input(database="loja-prod", schema_name="loja-prod")
    assert mongodb.database == mongodb.schema_name == "loja-prod"  # hyphens are valid in MongoDB
