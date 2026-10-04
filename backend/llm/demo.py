"""Explicit scripted demonstration. This is not an LLM or a natural-language classifier."""

import unicodedata

from backend.llm.base import ProviderReply
from backend.models.analysis import IntentDecision, QueryParameter, SQLDraft

DEMO_QUESTIONS = {
    "Quantos clientes foram cadastrados em setembro de 2026?": ("new_customers", "total"),
    "Qual foi a receita recebida em setembro de 2026?": ("received_revenue", "total"),
    "Quais regiões tiveram maior receita recebida em setembro de 2026?": (
        "received_revenue",
        "region",
    ),
    "Como a receita recebida evoluiu de janeiro a setembro de 2026?": ("received_revenue", "month"),
    "Quantos pedidos foram cancelados em setembro de 2026?": ("cancelled_orders", "total"),
}


def normalize_question(value: str) -> str:
    return " ".join(
        "".join(
            character
            for character in unicodedata.normalize("NFD", value.lower())
            if not unicodedata.combining(character)
        )
        .strip(" ?.!\n")
        .split()
    )


class DemoProvider:
    name = "demo"
    model = None
    is_demo = True

    async def complete(self, schema, instructions, payload):
        if schema is IntentDecision:
            match = next(
                (
                    entry
                    for question, entry in DEMO_QUESTIONS.items()
                    if normalize_question(question) == normalize_question(payload["question"])
                ),
                None,
            )
            if match is None:
                return ProviderReply(
                    IntentDecision(
                        action="clarification",
                        metric=None,
                        dimension="total",
                        start_date=None,
                        end_date=None,
                        region=None,
                        clarification_question="Use uma pergunta do README no modo demonstração.",
                    )
                )
            metric, dimension = match
            return ProviderReply(
                IntentDecision(
                    action="analyze",
                    metric=metric,
                    dimension=dimension,
                    region=None,
                    start_date="2026-01-01" if dimension == "month" else "2026-09-01",
                    end_date="2026-10-01",
                    clarification_question=None,
                )
            )
        plan = payload["plan"]
        metric, dimension = plan["metric"], plan["dimension"]
        if metric == "new_customers":
            sql = "SELECT COUNT(id) AS new_customers FROM analytics.customers "
            sql += "WHERE created_at >= :start_date AND created_at < :end_date"
        elif metric == "cancelled_orders":
            sql = "SELECT COUNT(id) AS cancelled_orders FROM analytics.orders "
            sql += "WHERE status = 'cancelled' "
            sql += "AND cancelled_at >= :start_date AND cancelled_at < :end_date"
        elif dimension == "region":
            sql = "SELECT r.name AS region, SUM(p.amount) AS received_revenue "
            sql += "FROM analytics.payments p "
            sql += "JOIN analytics.orders o ON o.id = p.order_id "
            sql += "JOIN analytics.customers c ON c.id = o.customer_id "
            sql += "JOIN analytics.regions r ON r.id = c.region_id WHERE p.status = 'completed' "
            sql += "AND p.completed_at >= :start_date AND p.completed_at < :end_date "
            sql += "GROUP BY r.name ORDER BY received_revenue DESC, r.name"
        elif dimension == "month":
            sql = "SELECT date_trunc('month', completed_at AT TIME ZONE 'America/Sao_Paulo')::date "
            sql += "AS month, SUM(amount) AS received_revenue FROM analytics.payments "
            sql += "WHERE status = 'completed' AND completed_at >= :start_date "
            sql += "AND completed_at < :end_date GROUP BY month ORDER BY month"
        else:
            sql = "SELECT COALESCE(SUM(amount), 0) AS received_revenue FROM analytics.payments "
            sql += "WHERE status = 'completed' AND completed_at >= :start_date "
            sql += "AND completed_at < :end_date"
        return ProviderReply(
            SQLDraft(
                sql=sql,
                parameters=[
                    QueryParameter(name=name, value=value)
                    for name, value in plan["parameters"].items()
                ],
            )
        )
