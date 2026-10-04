"""Static reference queries, unrelated to generated/user SQL."""

from backend.sample.data import PERIOD_END, PERIOD_START, START

QUESTIONS = [
    {
        "id": "new_customers",
        "question": "Quantos clientes foram cadastrados em setembro de 2026?",
        "sql": "SELECT COUNT(id) AS new_customers FROM analytics.customers "
        "WHERE created_at >= %s AND created_at < %s",
        "parameters": [PERIOD_START, PERIOD_END],
    },
    {
        "id": "received_revenue",
        "question": "Qual foi a receita recebida em setembro de 2026?",
        "sql": "SELECT COALESCE(SUM(amount), 0) AS received_revenue FROM analytics.payments "
        "WHERE status = 'completed' AND completed_at >= %s AND completed_at < %s",
        "parameters": [PERIOD_START, PERIOD_END],
    },
    {
        "id": "revenue_by_region",
        "question": "Quais regiões tiveram maior receita recebida em setembro de 2026?",
        "sql": "SELECT r.name AS region, SUM(p.amount) AS received_revenue "
        "FROM analytics.payments AS p "
        "JOIN analytics.orders AS o ON o.id = p.order_id "
        "JOIN analytics.customers AS c ON c.id = o.customer_id "
        "JOIN analytics.regions AS r ON r.id = c.region_id "
        "WHERE p.status = 'completed' AND p.completed_at >= %s AND p.completed_at < %s "
        "GROUP BY r.name ORDER BY received_revenue DESC, r.name ASC",
        "parameters": [PERIOD_START, PERIOD_END],
    },
    {
        "id": "monthly_revenue",
        "question": "Como a receita recebida evoluiu de janeiro a setembro de 2026?",
        "sql": "SELECT date_trunc('month', completed_at AT TIME ZONE 'America/Sao_Paulo')"
        "::date AS month, SUM(amount) AS received_revenue FROM analytics.payments "
        "WHERE status = 'completed' AND completed_at >= %s AND completed_at < %s "
        "GROUP BY month ORDER BY month",
        "parameters": [START, PERIOD_END],
    },
    {
        "id": "cancelled_orders",
        "question": "Quantos pedidos foram cancelados em setembro de 2026?",
        "sql": "SELECT COUNT(id) AS cancelled_orders FROM analytics.orders "
        "WHERE status = 'cancelled' AND cancelled_at >= %s AND cancelled_at < %s",
        "parameters": [PERIOD_START, PERIOD_END],
    },
]
