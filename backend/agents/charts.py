"""Deterministic check of the chart the model asked for, against the rows actually returned.

The model only names a chart type and two output columns; it never writes drawing code. A chart
that does not fit the data is dropped with a note instead of being drawn misleadingly.
"""

from backend.agents.narrative import to_decimal
from backend.models.analysis import ChartSpec
from backend.models.query import QueryResult

CHART_NAMES = {"bar": "barras", "line": "linha", "scatter": "dispersão", "pie": "pizza"}
# Rows each chart can show legibly.
LIMITS = {"bar": (2, 50), "line": (2, 500), "scatter": (3, 2000), "pie": (2, 8)}


def _numeric(rows: list[dict], column: str) -> list:
    return [to_decimal(row.get(column)) for row in rows]


def check_chart(
    spec: ChartSpec | None, query: QueryResult | None
) -> tuple[ChartSpec | None, str | None]:
    """The chart to draw (columns resolved to the result's names), or a note saying why not."""
    if spec is None or query is None or query.status != "success" or not query.rows:
        return None, None
    name = CHART_NAMES[spec.type]

    def refuse(reason: str) -> tuple[None, str]:
        return (
            None,
            f"O gráfico de {name} pedido não foi desenhado: {reason}. Os dados aparecem em tabela.",
        )

    columns = {column.lower(): column for column in query.columns}
    x, y = columns.get(spec.x.lower()), columns.get(spec.y.lower())
    if x is None or y is None:
        return refuse("as colunas indicadas não estão no resultado")
    if x == y:
        return refuse("o eixo e o valor precisam ser colunas diferentes")
    low, high = LIMITS[spec.type]
    if not low <= len(query.rows) <= high:
        return refuse(
            f"esse tipo funciona com {low} a {high} linhas e o resultado tem {len(query.rows)}"
        )
    values = _numeric(query.rows, y)
    if any(value is None for value in values):
        return refuse(f"a coluna {y} não é numérica em todas as linhas")
    if spec.type == "scatter" and any(value is None for value in _numeric(query.rows, x)):
        return refuse(f"a dispersão precisa de duas colunas numéricas e {x} não é")
    if spec.type == "pie":
        if any(value < 0 for value in values) or sum(values) <= 0:
            return refuse("a pizza só representa partes positivas de um total")
    return ChartSpec(type=spec.type, x=x, y=y), None
