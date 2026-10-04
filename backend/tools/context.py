from datetime import date, datetime, time
from importlib.resources import files
from zoneinfo import ZoneInfo

import yaml

from backend.models.analysis import IntentDecision, MetricEvidence, Period


class ContextError(Exception):
    pass


class SemanticContext:
    def __init__(self):
        self.schema = yaml.safe_load(
            files("backend").joinpath("semantic/schema.yaml").read_text("utf-8")
        )
        self.metrics = yaml.safe_load(
            files("backend").joinpath("semantic/metrics.yaml").read_text("utf-8")
        )

    def intent_context(self, exploration_enabled: bool = False) -> dict:
        context = {"metrics": self.metrics, "available_dimensions": ["total", "region", "month"]}
        context["exploration_enabled"] = exploration_enabled
        if exploration_enabled:
            context["schema"] = {
                table: list(spec["columns"]) for table, spec in self.schema["tables"].items()
            }
        return context

    def capabilities(self) -> dict:
        """What the assistant can tell about itself; never data values."""
        return {
            "domain": "Dados sintéticos de e-commerce, somente leitura.",
            "views": {
                table: {"grain": spec["grain"], "columns": list(spec["columns"])}
                for table, spec in self.schema["tables"].items()
            },
            "metrics": {
                name: metric["description"] for name, metric in self.metrics["metrics"].items()
            },
            "timezone": self.metrics["timezone"],
            "currency": self.metrics["currency"],
        }

    def explore_context(self) -> dict:
        # Only the approved analytics views; core tables and sensitive columns are never listed.
        return {
            "schema": self.schema["tables"],
            "metrics": self.metrics["metrics"],
            "conventions": {
                "dialect": "postgres",
                "qualifier": "analytics",
                "dates": "date_trunc('month', coluna AT TIME ZONE 'America/Sao_Paulo')",
                "timezone": self.metrics["timezone"],
                "currency": self.metrics["currency"],
                "interval": self.metrics["interval_convention"],
            },
        }

    @staticmethod
    def explore_plan() -> dict:
        return {
            "mode": "exploration",
            "operational_plan": [
                "Classificar a pergunta como exploratória, fora das métricas versionadas.",
                "Gerar um único SELECT sobre as views aprovadas do schema analytics.",
                "Validar com a mesma política determinística e executar somente leitura.",
                "Apresentar as linhas retornadas, o SQL executado e as premissas declaradas.",
            ],
            "limitations": [
                "Consulta exploratória: a definição não é uma métrica versionada; "
                "confira o SQL e as premissas antes de usar o número.",
            ],
        }

    def retrieve(self, intent: IntentDecision) -> dict:
        tables = {
            "new_customers": ["customers"],
            "cancelled_orders": ["orders"],
            "received_revenue": ["payments"],
        }[intent.metric]
        if intent.dimension == "region" or intent.region:
            tables = list(dict.fromkeys(tables + ["orders", "customers", "regions"]))
        return {
            "schema": {table: self.schema["tables"][table] for table in tables},
            "metric": {"name": intent.metric, **self.metrics["metrics"][intent.metric]},
            "timezone": "America/Sao_Paulo",
        }

    def plan(self, intent: IntentDecision) -> dict:
        if intent.metric is None or intent.start_date is None or intent.end_date is None:
            raise ContextError("Informe a métrica e o período de análise.")
        try:
            start, end = date.fromisoformat(intent.start_date), date.fromisoformat(intent.end_date)
        except ValueError:
            raise ContextError("Informe um período com datas válidas.") from None
        if start >= end or (end - start).days > 366:
            raise ContextError("Escolha um período válido de até 366 dias.")
        if intent.metric != "received_revenue" and (intent.dimension != "total" or intent.region):
            raise ContextError(
                "Neste MVP, essa métrica está disponível apenas como total sem região."
            )
        metric = self.metrics["metrics"][intent.metric]
        timezone = ZoneInfo("America/Sao_Paulo")
        parameters = {
            "start_date": datetime.combine(start, time.min, tzinfo=timezone).isoformat(),
            "end_date": datetime.combine(end, time.min, tzinfo=timezone).isoformat(),
        }
        if intent.region:
            parameters["region"] = intent.region
        columns = [intent.metric]
        if intent.dimension != "total":
            columns.insert(0, intent.dimension)
        return {
            "metric": intent.metric,
            "dimension": intent.dimension,
            "period": Period(start=start, end_exclusive=end),
            "parameters": parameters,
            "output_columns": columns,
            "region": intent.region,
            "metric_evidence": MetricEvidence(
                name=intent.metric,
                version=metric["version"],
                description=metric["description"],
                unit=metric["unit"],
            ),
            "operational_plan": [
                f"Usar a definição versionada de {intent.metric}.",
                f"Filtrar por {metric['date_column']} no período, com fim exclusivo.",
                f"Aplicar agregação e dimensão {intent.dimension}.",
                "Validar e executar uma consulta somente de leitura.",
                "Apresentar valores retornados, SQL e limitações.",
            ],
            "limitations": metric.get("limitations", []),
        }
