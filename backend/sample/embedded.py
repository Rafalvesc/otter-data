"""The sample base without Docker: the same synthetic data in a local, read-only DuckDB file.

Used when no PostgreSQL credentials are configured (the installed desktop app). It has the
same tables as the PostgreSQL `analytics` views, minus the personal `email` column, and works
in exploration mode; the versioned-metric documentation travels as context for the model.
"""

import csv
import tempfile
from datetime import UTC, datetime, timedelta, timezone
from importlib.resources import files
from pathlib import Path

import duckdb
import yaml

from backend.config import Settings
from backend.sample.data import COLUMNS, DATASET_VERSION, generate_dataset
from backend.sources.catalog import SENSITIVE_COLUMN
from backend.sources.context import CatalogContext
from backend.sources.engines import Connection, discover
from backend.sources.executor import SourceExecutor
from backend.sources.models import SourceConfig
from backend.sources.registry import SAMPLE_ID, SourceRuntime, default_data_dir
from backend.tools.sql_validator import SQLValidator

SAMPLE_NAME = "Exemplo: e-commerce sintético"
LOCAL = timezone(timedelta(hours=-3))  # the generator's America/Sao_Paulo offset (no DST in 2026)
TYPES = {
    "id": "INTEGER",
    "region_id": "INTEGER",
    "customer_id": "INTEGER",
    "order_id": "INTEGER",
    "product_id": "INTEGER",
    "quantity": "INTEGER",
    "name": "VARCHAR",
    "state": "VARCHAR",
    "category": "VARCHAR",
    "status": "VARCHAR",
    "current_price": "DECIMAL(12,2)",
    "unit_price": "DECIMAL(12,2)",
    "amount": "DECIMAL(12,2)",
    "created_at": "TIMESTAMP",
    "ordered_at": "TIMESTAMP",
    "cancelled_at": "TIMESTAMP",
    "completed_at": "TIMESTAMP",
}


def _local(value):
    # Timestamps are stored as São Paulo wall-clock time, like the PostgreSQL session timezone.
    if isinstance(value, datetime):
        return value.astimezone(LOCAL).replace(tzinfo=None)
    return value


def build_database(path: Path) -> Path:
    """Write the sample tables once; the file name carries the dataset version."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".tmp")
    partial.unlink(missing_ok=True)
    data = generate_dataset()
    with tempfile.TemporaryDirectory() as staging, duckdb.connect(str(partial)) as conn:
        for table, columns in COLUMNS.items():
            kept = [column for column in columns if not SENSITIVE_COLUMN.search(column)]
            definition = ", ".join(f'"{column}" {TYPES[column]}' for column in kept)
            conn.execute(f'CREATE TABLE "{table}" ({definition})')
            # Bulk load through a CSV file: row-by-row inserts take minutes for ~30k rows.
            staged = Path(staging) / f"{table}.csv"
            with staged.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                for row in data[table]:
                    writer.writerow("" if row[c] is None else _local(row[c]) for c in kept)
            # Empty CSV fields load as NULL; the path is our own temporary file.
            source = str(staged).replace("'", "''")
            conn.execute(f"COPY \"{table}\" FROM '{source}' (FORMAT csv, HEADER false)")
    partial.replace(path)
    return path


def profile() -> dict:
    """Documentation for the model: the versioned metrics and table notes, as text."""
    root = files("backend").joinpath("semantic")
    metrics = yaml.safe_load(root.joinpath("metrics.yaml").read_text("utf-8"))
    schema = yaml.safe_load(root.joinpath("schema.yaml").read_text("utf-8"))
    documented = {
        name: {
            "description": metric["description"],
            "formula": metric["formula"].replace("analytics.", ""),
            "filters": metric.get("filters"),
            "date_column": metric["date_column"],
            "unit": metric["unit"],
            "limitations": metric.get("limitations", []),
        }
        for name, metric in metrics["metrics"].items()
    }
    notes = {
        table: {key: spec[key] for key in ("grain", "status_values", "notes") if key in spec}
        for table, spec in schema["tables"].items()
    }
    return {
        "label": f"{SAMPLE_NAME} (base embutida)",
        "domain": "Dados sintéticos de e-commerce gerados localmente, somente leitura.",
        "metrics": documented,
        "documentation": notes,
        "conventions": {
            "timestamps": "Horário de São Paulo sem fuso (TIMESTAMP). Use datas ISO sem offset, "
            "ex.: '2026-09-01' ou '2026-09-01 00:00:00'.",
            "currency": metrics["currency"],
        },
        "limitations": [
            "Base local sintética; não representa uma empresa real.",
            "Base de exemplo embutida (sem PostgreSQL): as métricas documentadas orientam o SQL, "
            "mas não são versionadas como no modo com Docker.",
        ],
    }


def embedded_sample_runtime(settings: Settings) -> SourceRuntime:
    data_dir = Path(settings.data_dir) if settings.data_dir else default_data_dir()
    path = build_database(data_dir / f"sample-{DATASET_VERSION}.duckdb")
    connection = Connection(kind="csv", path=path)
    catalog = discover(connection, "main", timeout=settings.query_timeout_seconds)
    config = SourceConfig(
        id=SAMPLE_ID,
        name=SAMPLE_NAME,
        kind="csv",
        schema_name="main",
        allow_rows_to_llm=True,
        created_at=datetime.now(UTC).isoformat(),
    )
    validator = SQLValidator(
        {name: spec.model_dump() for name, spec in catalog.tables.items()},
        schema="main",
        dialect="duckdb",
    )
    return SourceRuntime(
        id=SAMPLE_ID,
        name=SAMPLE_NAME,
        kind="sample",
        context=CatalogContext(config, catalog, profile()),
        validator=validator,
        executor=SourceExecutor(settings, validator, connection),
        allow_rows_to_llm=True,
        metrics_enabled=False,
    )
