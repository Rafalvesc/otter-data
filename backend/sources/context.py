"""What the model may know about a connected source: structure only, never values."""

from backend.models.analysis import IntentDecision
from backend.sources.models import Catalog, SourceConfig
from backend.tools.context import ContextError

DIALECT = {"postgres": "postgres", "mysql": "mysql", "csv": "duckdb", "mongodb": "duckdb"}
KIND_LABEL = {
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "csv": "CSV importado (DuckDB)",
    "mongodb": "MongoDB, cópia local em DuckDB",
}
DATE_HINT = {
    "postgres": "date_trunc('month', coluna) para agrupar por mês",
    "mysql": "DATE_FORMAT(coluna, '%Y-%m-01') para agrupar por mês; YEAR(coluna), MONTH(coluna)",
    "duckdb": "date_trunc('month', coluna) para agrupar por mês",
}


class CatalogContext:
    """Same interface as SemanticContext for a source without versioned metrics."""

    metrics_enabled = False

    def __init__(
        self,
        config: SourceConfig,
        catalog: Catalog,
        profile: dict | None = None,
        values: dict[str, dict[str, list[str]]] | None = None,
    ):
        self.config = config
        self.catalog = catalog
        # Possible values of low-cardinality text columns, only for sources whose results the
        # model may read (see SourceRegistry.categorical_values).
        self.values = values or {}
        self.dialect = DIALECT[config.kind]
        # Optional documentation for a known base (the embedded sample): label, domain,
        # metric definitions and table notes. Never data values.
        self.profile = profile or {}

    def _schema(self) -> dict:
        schema = {
            table: {"columns": spec.columns, "relationships": spec.relationships}
            for table, spec in self.catalog.tables.items()
        }
        for table, columns in self.values.items():
            if table in schema:
                schema[table]["values"] = columns
        return schema

    def intent_context(self, exploration_enabled: bool = True) -> dict:
        return {
            "source": self.profile.get("label")
            or f"{self.config.name} ({KIND_LABEL[self.config.kind]})",
            "metrics": {},
            "available_dimensions": [],
            "exploration_enabled": True,
            "schema": {table: list(spec.columns) for table, spec in self.catalog.tables.items()},
            "note": "Esta base não tem métricas versionadas: perguntas sobre dados usam explore.",
        }

    def capabilities(self) -> dict:
        return {
            "domain": self.profile.get("domain")
            or f"Base conectada pelo usuário: {self.config.name} "
            f"({KIND_LABEL[self.config.kind]}), somente leitura.",
            # Names and types only (never values), so the assistant can explain the structure.
            "views": {
                table: {"columns": dict(spec.columns)}
                for table, spec in self.catalog.tables.items()
            },
            "metrics": {
                name: metric["description"]
                for name, metric in self.profile.get("metrics", {}).items()
            },
        }

    def explore_context(self) -> dict:
        context = {
            "schema": self._schema(),
            "metrics": self.profile.get("metrics", {}),
            "conventions": {
                "dialect": self.dialect,
                "qualifier": self.config.schema_name,
                "dates": DATE_HINT[self.dialect],
                "note": "Estrutura descoberta automaticamente; colunas com possíveis dados "
                "pessoais foram ocultadas e não podem ser usadas.",
            },
        }
        if self.profile.get("documentation"):
            context["documentation"] = self.profile["documentation"]
        context["conventions"].update(self.profile.get("conventions", {}))
        return context

    def explore_plan(self) -> dict:
        return {
            "mode": "exploration",
            "operational_plan": [
                "Classificar a pergunta como exploratória sobre a base conectada.",
                f"Gerar um único SELECT em {self.dialect} sobre as tabelas descobertas.",
                "Validar com a política determinística e executar em transação somente leitura.",
                "Apresentar as linhas retornadas, o SQL executado e as premissas declaradas.",
            ],
            "limitations": self.profile.get("limitations")
            or [
                "Base conectada pelo usuário: a estrutura foi descoberta automaticamente e não há "
                "métricas versionadas; confira o SQL e as premissas antes de usar o número.",
                "Colunas com nomes que sugerem dados pessoais ou secretos foram ocultadas.",
            ],
        }

    def retrieve(self, intent: IntentDecision) -> dict:
        raise ContextError("Esta base não possui métricas versionadas.")

    def plan(self, intent: IntentDecision) -> dict:
        raise ContextError("Esta base não possui métricas versionadas.")
