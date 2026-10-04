"""Schema discovery for connected sources.

Only plain lowercase identifiers are exposed. Columns whose names suggest personal or secret
data are hidden: they never reach the model and the validator cannot resolve them.
"""

import re
from collections.abc import Iterable

from backend.sources.models import Catalog, CatalogTable

PLAIN_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
SENSITIVE_COLUMN = re.compile(
    r"(e_?mail|phone|fone|telefone|celular|whats|cpf|cnpj|^rg$|_rg$|ssn|tax_?id|passw|senha|"
    r"token|secret|api_?key|card|cartao|cvv|iban|address|endereco|street|logradouro|"
    r"^cep$|_cep$|zip|birth|nascimento|salary|salario)"
)
MAX_TABLES = 80
MAX_COLUMNS = 150


def is_sensitive(column: str) -> bool:
    return bool(SENSITIVE_COLUMN.search(column))


def build_catalog(
    columns: Iterable[tuple[str, str, str]],
    foreign_keys: Iterable[tuple[str, str, str, str]] = (),
) -> Catalog:
    """columns: (table, column, type) rows; foreign_keys: (table, column, ref_table, ref_column)."""
    tables: dict[str, CatalogTable] = {}
    skipped: list[str] = []
    for table, column, kind in columns:
        if not PLAIN_IDENTIFIER.match(table):
            if f"tabela {table}" not in skipped:
                skipped.append(f"tabela {table}")
            continue
        if table not in tables:
            if len(tables) >= MAX_TABLES:
                skipped.append(f"tabela {table} (limite de {MAX_TABLES} tabelas)")
                continue
            tables[table] = CatalogTable(columns={})
        entry = tables[table]
        if not PLAIN_IDENTIFIER.match(column):
            skipped.append(f"coluna {table}.{column}")
        elif is_sensitive(column):
            entry.hidden_columns.append(column)
        elif len(entry.columns) >= MAX_COLUMNS:
            skipped.append(f"coluna {table}.{column} (limite de {MAX_COLUMNS} colunas)")
        else:
            entry.columns[column] = str(kind or "text").lower()
    tables = {name: table for name, table in tables.items() if table.columns}

    def link(table: str, column: str, ref_table: str, ref_column: str) -> None:
        if (
            table in tables
            and ref_table in tables
            and column in tables[table].columns
            and ref_column in tables[ref_table].columns
        ):
            tables[table].relationships.setdefault(column, f"{ref_table}.{ref_column}")

    for table, column, ref_table, ref_column in foreign_keys:
        link(table, column, ref_table, ref_column)
    # Views and CSV imports have no declared keys: infer <name>_id -> <name>[s|es].id.
    for table, entry in tables.items():
        for column in list(entry.columns):
            if column.endswith("_id") and column not in entry.relationships:
                base = column[:-3]
                for candidate in (base, f"{base}s", f"{base}es"):
                    if (
                        candidate != table
                        and candidate in tables
                        and "id" in tables[candidate].columns
                    ):
                        link(table, column, candidate, "id")
                        break
    return Catalog(tables=tables, skipped=skipped)


POSTGRES_COLUMNS = """
SELECT c.table_name, c.column_name, c.data_type
FROM information_schema.columns AS c
JOIN information_schema.tables AS t
  ON t.table_schema = c.table_schema AND t.table_name = c.table_name
WHERE c.table_schema = %s AND t.table_type IN ('BASE TABLE', 'VIEW')
ORDER BY c.table_name, c.ordinal_position
"""

POSTGRES_FOREIGN_KEYS = """
SELECT kcu.table_name, kcu.column_name, ccu.table_name, ccu.column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s
"""

MYSQL_COLUMNS = """
SELECT c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE
FROM information_schema.COLUMNS AS c
JOIN information_schema.TABLES AS t
  ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME
WHERE c.TABLE_SCHEMA = %s AND t.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION
"""

MYSQL_FOREIGN_KEYS = """
SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL
"""

DUCKDB_COLUMNS = """
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'main'
ORDER BY table_name, ordinal_position
"""
