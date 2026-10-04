import json

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.agents.analyst import AnalystService
from backend.api.sources import get_source_registry
from backend.config import Settings
from backend.main import app
from backend.models.analysis import AskRequest, ExploratoryDraft
from backend.runtime import create_loop
from backend.sources.catalog import build_catalog
from backend.sources.models import DatabaseSourceInput, SourceUpdate
from backend.sources.registry import RegistryError, SourceRegistry
from backend.tools.sql_validator import SQLValidator
from tests.helpers import ScriptedProvider, intent, run

SALES_CSV = (
    "Data da Venda;Produto;Valor (R$);E-mail Cliente;Região\n"
    "2026-01-05;Caneca;35.5;a@x.com;Sul\n"
    "2026-01-20;Caderno;12;b@x.com;Norte\n"
    "2026-02-02;Caneca;35.5;c@x.com;Sul\n"
)


class MemorySecrets:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)


def settings(**values):
    return Settings(
        _env_file=None,
        analytics_password="offline-db-secret",
        **values,
    )


@pytest.fixture
def registry(tmp_path):
    return SourceRegistry(settings(), secrets=MemorySecrets(), data_dir=tmp_path / "data")


@pytest.fixture
def sales(tmp_path, registry):
    path = tmp_path / "Vendas 2026.csv"
    path.write_text(SALES_CSV, encoding="utf-8")
    return registry.add_csv("Minhas vendas", path.name, path, allow_rows_to_llm=False)


# ---------------------------------------------------------------- catalog


def test_catalog_hides_personal_columns_and_skips_unsafe_identifiers():
    catalog = build_catalog(
        [
            ("customers", "id", "int"),
            ("customers", "email", "varchar"),
            ("customers", "cpf", "varchar"),
            ("customers", "city", "varchar"),
            ("orders", "id", "int"),
            ("orders", "customer_id", "int"),
            ("orders", "Total Value", "decimal"),
            ("Weird Table", "id", "int"),
        ]
    )
    assert set(catalog.tables) == {"customers", "orders"}
    assert catalog.tables["customers"].hidden_columns == ["email", "cpf"]
    assert list(catalog.tables["customers"].columns) == ["id", "city"]
    assert catalog.tables["orders"].relationships == {"customer_id": "customers.id"}
    assert (
        "coluna orders.Total Value" in catalog.skipped and "tabela Weird Table" in catalog.skipped
    )


def test_declared_foreign_keys_win_and_must_point_to_visible_columns():
    catalog = build_catalog(
        [("a", "id", "int"), ("a", "owner", "int"), ("b", "id", "int"), ("b", "email", "text")],
        [("a", "owner", "b", "id"), ("a", "id", "b", "email")],
    )
    assert catalog.tables["a"].relationships == {"owner": "b.id"}


# ---------------------------------------------------------------- validator per dialect

SHOP = {
    "orders": {
        "columns": {
            "id": "int",
            "customer_id": "int",
            "created_at": "datetime",
            "note": "varchar(99)",
        },
        "relationships": {"customer_id": "customers.id"},
    },
    "customers": {"columns": {"id": "int", "city": "varchar(60)"}},
}


def test_mysql_uses_positional_placeholders_and_escapes_literal_percent():
    validator = SQLValidator(SHOP, schema="shop", dialect="mysql")
    prepared = validator.prepare(
        "SELECT DATE_FORMAT(o.created_at, '%Y-%m-01') AS month, COUNT(*) AS n FROM shop.orders o "
        "WHERE o.created_at >= :start AND o.note LIKE '%ok%' AND o.created_at < :end GROUP BY 1",
        {"end": "2027-01-01", "start": "2026-01-01"},
    )
    sql = prepared.validation.normalized_sql
    assert prepared.validation.allowed and sql.count("%s") == 2
    assert "'%%Y-%%m-01'" in sql and "'%%ok%%'" in sql
    assert prepared.parameter_values == ("2026-01-01", "2027-01-01")


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("SELECT c.city FROM other.customers c", "relation_not_allowed"),
        ("SELECT o.id FROM shop.orders o JOIN shop.customers c ON o.id = c.id", "join_not_allowed"),
        ("SELECT SLEEP(5) AS s FROM shop.orders", "function_not_allowed"),
        ("SELECT c.email FROM shop.customers c", "column_not_allowed"),
        ("UPDATE shop.orders SET note = 'x'", "read_only_required"),
    ],
)
def test_connected_source_policy_rejections(sql, code):
    assert SQLValidator(SHOP, schema="shop", dialect="mysql").validate(sql).code == code


def test_duckdb_and_postgres_keep_numbered_placeholders():
    duck = SQLValidator(
        {"sales": {"columns": {"sold_at": "TIMESTAMP"}}}, schema="main", dialect="duckdb"
    )
    prepared = duck.prepare(
        "SELECT date_trunc('month', s.sold_at) AS m FROM main.sales s WHERE s.sold_at >= :a",
        {"a": "2026-01-01"},
    )
    assert prepared.validation.allowed and "$1" in prepared.validation.normalized_sql
    with pytest.raises(ValueError):
        SQLValidator(SHOP, schema="shop", dialect="oracle")


# ---------------------------------------------------------------- registry


def test_csv_source_is_imported_with_clean_names_and_queried_read_only(registry, sales):
    detail = registry.detail(sales.id)
    table = detail.catalog["vendas_2026"]
    assert list(table.columns) == ["data_da_venda", "produto", "valor_r", "regiao"]
    assert table.hidden_columns == ["e_mail_cliente"] and sales.hidden_columns == 1
    executor = registry.runtime(sales.id).executor
    result = run(
        executor.execute_async(
            "SELECT v.produto AS produto, SUM(v.valor_r) AS total FROM main.vendas_2026 v "
            "WHERE v.data_da_venda >= :inicio GROUP BY v.produto ORDER BY total DESC",
            {"inicio": "2026-01-01"},
        )
    )
    assert result.status == "success" and result.rows == [
        {"produto": "Caneca", "total": 71.0},
        {"produto": "Caderno", "total": 12.0},
    ]
    for sql in ("SELECT v.e_mail_cliente FROM main.vendas_2026 v", "DROP TABLE main.vendas_2026"):
        assert run(executor.execute_async(sql)).status == "denied"


def test_chat_capabilities_describe_structure_without_values_or_hidden_columns(registry, sales):
    capabilities = registry.runtime(sales.id).context.capabilities()
    columns = capabilities["views"]["vendas_2026"]["columns"]
    assert list(columns) == ["data_da_venda", "produto", "valor_r", "regiao"]
    text = json.dumps(capabilities)
    assert "e_mail_cliente" not in text and "Caneca" not in text


def test_more_csv_files_become_tables_and_settings_can_change(tmp_path, registry, sales):
    extra = tmp_path / "metas.csv"
    extra.write_text("mes,meta\n2026-01-01,40\n", encoding="utf-8")
    assert registry.add_csv_table(sales.id, extra.name, extra).tables == 2
    updated = registry.update(sales.id, SourceUpdate(allow_rows_to_llm=True, name="Vendas"))
    assert updated.allow_rows_to_llm and updated.name == "Vendas"
    assert registry.runtime(sales.id).allow_rows_to_llm


def test_delete_removes_config_catalog_database_and_secret(tmp_path, registry, sales):
    registry.delete(sales.id)
    assert registry.summaries() == []
    assert not list((registry.root / "sources").glob(f"{sales.id}*"))
    with pytest.raises(RegistryError):
        registry.runtime(sales.id)


def test_invalid_csv_is_rejected_without_leaving_files(tmp_path, registry):
    bad = tmp_path / "vazio.csv"
    bad.write_text("\n\n", encoding="utf-8")
    with pytest.raises(RegistryError):
        registry.add_csv("Ruim", bad.name, bad, False)
    assert not list((registry.root / "sources").glob("*.duckdb"))


def test_database_password_goes_to_the_vault_not_to_disk(tmp_path, monkeypatch):
    secrets = MemorySecrets()
    registry = SourceRegistry(settings(), secrets=secrets, data_dir=tmp_path)
    monkeypatch.setattr(
        "backend.sources.registry.discover",
        lambda connection, schema, timeout: build_catalog([("orders", "id", "int")]),
    )
    summary = registry.add_database(
        DatabaseSourceInput(
            name="Loja",
            kind="mysql",
            host="db.local",
            port=3306,
            database="shop",
            user="reader",
            password=SecretStr("super-secret-pw"),
        )
    )
    assert secrets.values == {summary.id: "super-secret-pw"}
    stored = "".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.json"))
    assert "super-secret-pw" not in stored and summary.schema_name == "shop"
    assert "super-secret-pw" not in summary.model_dump_json()


# ---------------------------------------------------------------- analysis on a connected source


def explore_draft(sql):
    return ExploratoryDraft(sql=sql, parameters=[], title="Vendas por produto", assumptions=[])


def test_analysis_on_csv_source_explores_and_keeps_rows_away_from_the_model(registry, sales):
    sql = (
        "SELECT v.produto AS produto, SUM(v.valor_r) AS total FROM main.vendas_2026 v "
        "GROUP BY v.produto ORDER BY total DESC"
    )
    provider = ScriptedProvider(
        intent(action="analyze", metric="received_revenue"), explore_draft(sql)
    )
    analyst = AnalystService(settings(narrative_enabled=True), provider, sources=registry)
    response = run(
        analyst.ask(AskRequest(question="Quanto vendi por produto?", source_id=sales.id))
    )
    assert response.status == "success" and response.analysis_mode == "exploration"
    assert response.source_id == sales.id and response.source_name == "Minhas vendas"
    assert response.query.rows[0] == {"produto": "Caneca", "total": 71.0}
    assert response.narrative is None and "não permite que a IA leia" in response.narrative_note
    assert response.limitations[0] == "Base conectada pelo usuário: Minhas vendas."
    assert len(provider.payloads) == 2  # intent + SQL; no narration call with rows
    explore = provider.payloads[1]["context"]
    assert explore["conventions"]["dialect"] == "duckdb"
    assert explore["conventions"]["qualifier"] == "main"
    assert "e_mail_cliente" not in json.dumps(provider.payloads)
    assert provider.payloads[0]["context"]["metrics"] == {}


def test_unknown_source_is_reported_without_calling_the_model(registry):
    provider = ScriptedProvider()
    analyst = AnalystService(settings(), provider, sources=registry)
    response = run(analyst.ask(AskRequest(question="Oi", source_id="csv-doesnotexist")))
    assert response.status == "error" and response.code == "source_unavailable"
    assert provider.payloads == []


# ---------------------------------------------------------------- API


@pytest.fixture
def client(registry):
    app.dependency_overrides[get_source_registry] = lambda: registry
    try:
        with TestClient(app, backend_options={"loop_factory": create_loop}) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_sources_api_lists_imports_updates_and_deletes(client):
    listed = client.get("/api/v1/sources").json()
    assert listed["default"] == "sample" and listed["sources"][0]["built_in"] is True
    created = client.post(
        "/api/v1/sources/csv",
        params={"name": "Vendas", "filename": "Vendas 2026.csv"},
        content=SALES_CSV.encode(),
        headers={"Content-Type": "text/csv"},
    )
    assert created.status_code == 201 and created.json()["tables"] == 1
    source_id = created.json()["id"]
    detail = client.get(f"/api/v1/sources/{source_id}").json()
    assert "e_mail_cliente" in detail["catalog"]["vendas_2026"]["hidden_columns"]
    patched = client.patch(f"/api/v1/sources/{source_id}", json={"allow_rows_to_llm": True})
    assert patched.json()["allow_rows_to_llm"] is True
    assert client.delete(f"/api/v1/sources/{source_id}").status_code == 204
    assert len(client.get("/api/v1/sources").json()["sources"]) == 1


def test_cross_site_requests_are_refused(client):
    blocked = client.post(
        "/api/v1/sources/csv",
        params={"name": "x", "filename": "x.csv"},
        content=b"a,b\n1,2\n",
        headers={"Origin": "https://evil.example"},
    )
    assert blocked.status_code == 403
    assert (
        client.delete("/api/v1/sources/x", headers={"Sec-Fetch-Site": "cross-site"}).status_code
        == 403
    )


def test_csv_size_limit(client, monkeypatch):
    monkeypatch.setattr("backend.api.sources.get_settings", lambda: settings(csv_max_mb=1))
    response = client.post(
        "/api/v1/sources/csv",
        params={"name": "x", "filename": "x.csv"},
        content=b"a\n" + b"1\n" * (1024 * 1024),
    )
    assert response.status_code == 413


def test_database_input_never_echoes_the_password(client, monkeypatch, registry):
    def refuse(data):
        raise RegistryError(
            "Não foi possível conectar ao PostgreSQL; confira host, porta, usuário e senha."
        )

    monkeypatch.setattr(registry, "add_database", refuse)
    response = client.post(
        "/api/v1/sources/database",
        json={
            "name": "x",
            "kind": "postgres",
            "host": "127.0.0.1",
            "port": 5432,
            "database": "db",
            "user": "u",
            "password": "hunter2-secret",
        },
    )
    assert response.status_code == 400 and "hunter2-secret" not in response.text
