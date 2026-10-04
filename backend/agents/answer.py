from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from backend.models.query import QueryResult
from backend.sample.data import REGION_NAMES


class InvalidResult(Exception):
    pass


def display_value(value, monetary: bool) -> str:
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise InvalidResult("Resultado numérico inválido.") from None
    if not number.is_finite() or number < 0:
        raise InvalidResult("Resultado numérico inválido.")
    if not monetary and number != number.to_integral_value():
        raise InvalidResult("Contagem deve ser inteira.")
    value = f"{number:,.2f}" if monetary else f"{int(number):,}"
    localized = value.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {localized}" if monetary else localized


def render_answer(plan: dict, query: QueryResult, demo: bool) -> str:
    if query.columns != plan["output_columns"]:
        raise InvalidResult("Colunas retornadas não correspondem ao plano operacional.")
    period = plan["period"]
    start = period.start.strftime("%d/%m/%Y")
    last = (period.end_exclusive - timedelta(days=1)).strftime("%d/%m/%Y")
    prefix = "Modo demonstração, sem LLM. " if demo else ""
    if not query.rows:
        return prefix + f"Não foram retornados registros para os filtros de {start} a {last}."
    metric = plan["metric"]
    labels = {
        "received_revenue": "Receita recebida",
        "new_customers": "Clientes cadastrados",
        "cancelled_orders": "Pedidos cancelados",
    }
    if plan["dimension"] == "total":
        if len(query.rows) != 1:
            raise InvalidResult("Um total deve retornar exatamente uma linha.")
        value = display_value(query.rows[0][metric], metric == "received_revenue")
        return prefix + f"{labels[metric]} de {start} a {last}: {value}."
    dimension_label = {"region": "região", "month": "mês"}[plan["dimension"]]
    lines = [prefix + f"{labels[metric]} de {start} a {last}, por {dimension_label}:"]
    for row in query.rows:
        dimension = row[plan["dimension"]]
        if plan["dimension"] == "month":
            try:
                month = date.fromisoformat(dimension)
            except (ValueError, TypeError):
                raise InvalidResult("Data de agrupamento inválida.") from None
            if month.day != 1:
                raise InvalidResult("Mês de agrupamento inválido.")
            label = month.strftime("%m/%Y")
        else:
            if dimension not in REGION_NAMES:
                raise InvalidResult("Região de agrupamento inválida.")
            label = dimension
        value = display_value(row[metric], True)
        if len(lines) <= 5:
            lines.append(f"{label}: {value}.")
    if len(query.rows) > 5:
        lines.append(
            f"Exibidos cinco de {len(query.rows)} grupos; consulte os demais nas evidências."
        )
    if query.truncated:
        lines.append("O resultado foi truncado pelo limite de retorno; a lista está incompleta.")
    return "\n".join(lines)


def format_cell(value) -> str:
    if value is None:
        return "sem valor"
    if isinstance(value, bool):
        return "sim" if value else "não"
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return str(value)
    if not number.is_finite():
        raise InvalidResult("Resultado numérico inválido.")
    text = f"{number:,.2f}" if number != number.to_integral_value() else f"{int(number):,}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def render_exploration_answer(title: str, query: QueryResult) -> str:
    """Describe returned rows only; numbers come from the database, never from the model."""
    if not query.rows:
        return f"{title}: a consulta não retornou registros."
    if len(query.rows) == 1 and len(query.columns) <= 3:
        row = query.rows[0]
        values = "; ".join(f"{column} = {format_cell(row[column])}" for column in query.columns)
        return f"{title}: {values}."
    suffix = " (lista truncada pelo limite de retorno)" if query.truncated else ""
    return f"{title}: {query.row_count} linha(s) retornada(s){suffix}; veja a tabela."
