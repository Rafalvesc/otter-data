import pytest

from backend.agents.charts import check_chart
from backend.models.analysis import AskRequest, ChartSpec, ExploratoryDraft
from tests.helpers import intent, result, run, service

CATEGORIES = result(
    columns=["category", "revenue"],
    rows=[
        {"category": "Livros", "revenue": "1200.50"},
        {"category": "Casa", "revenue": "800"},
        {"category": "Esporte", "revenue": "450.25"},
    ],
    row_count=3,
)
POINTS = result(
    columns=["age", "cholesterol"],
    rows=[{"age": 40 + i, "cholesterol": 200 + 3 * i} for i in range(10)],
    row_count=10,
)


@pytest.mark.parametrize(
    ("spec", "query"),
    [
        (ChartSpec(type="bar", x="category", y="revenue"), CATEGORIES),
        (ChartSpec(type="pie", x="CATEGORY", y="Revenue"), CATEGORIES),
        (ChartSpec(type="line", x="category", y="revenue"), CATEGORIES),
        (ChartSpec(type="scatter", x="age", y="cholesterol"), POINTS),
    ],
)
def test_charts_that_fit_the_returned_rows_are_kept(spec, query):
    chart, note = check_chart(spec, query)
    assert note is None and chart.type == spec.type
    assert chart.x in query.columns and chart.y in query.columns  # resolved to real names


@pytest.mark.parametrize(
    ("spec", "query", "reason"),
    [
        (ChartSpec(type="bar", x="category", y="missing"), CATEGORIES, "não estão no resultado"),
        (ChartSpec(type="bar", x="revenue", y="revenue"), CATEGORIES, "colunas diferentes"),
        (ChartSpec(type="bar", x="revenue", y="category"), CATEGORIES, "não é numérica"),
        (
            ChartSpec(type="scatter", x="category", y="revenue"),
            CATEGORIES,
            "duas colunas numéricas",
        ),
        (ChartSpec(type="pie", x="age", y="cholesterol"), POINTS, "2 a 8 linhas"),
        (
            ChartSpec(type="pie", x="category", y="revenue"),
            result(
                columns=["category", "revenue"],
                rows=[{"category": "A", "revenue": 5}, {"category": "B", "revenue": -2}],
            ),
            "partes positivas",
        ),
    ],
)
def test_charts_that_do_not_fit_are_dropped_with_a_note(spec, query, reason):
    chart, note = check_chart(spec, query)
    assert chart is None and reason in note and "tabela" in note


def test_no_chart_requested_or_no_rows_means_no_chart_and_no_note():
    assert check_chart(None, CATEGORIES) == (None, None)
    empty = result(columns=["category", "revenue"], rows=[], row_count=0)
    assert check_chart(ChartSpec(type="bar", x="category", y="revenue"), empty) == (None, None)


def explore(sql, chart):
    return ExploratoryDraft(
        sql=sql, title="Receita por categoria", assumptions=[], parameters=[], chart=chart
    )


SQL = (
    "SELECT p.category AS category, SUM(i.quantity * i.unit_price) AS revenue "
    "FROM analytics.order_items i JOIN analytics.products p ON i.product_id = p.id "
    "GROUP BY p.category ORDER BY revenue DESC"
)


def test_requested_chart_reaches_the_response():
    explore_intent = intent(action="explore", metric=None, start_date=None, end_date=None)
    chart = ChartSpec(type="pie", x="category", y="revenue")
    analyst, _, _ = service(explore_intent, explore(SQL, chart), query_result=CATEGORIES)
    response = run(analyst.ask(AskRequest(question="Faça uma pizza da receita por categoria")))
    assert response.status == "success" and response.chart == chart


def test_unusable_chart_becomes_a_limitation_not_a_figure():
    explore_intent = intent(action="explore", metric=None, start_date=None, end_date=None)
    chart = ChartSpec(type="scatter", x="category", y="revenue")
    analyst, _, _ = service(explore_intent, explore(SQL, chart), query_result=CATEGORIES)
    response = run(analyst.ask(AskRequest(question="Dispersão da receita por categoria")))
    assert response.status == "success" and response.chart is None
    assert any("dispersão" in item for item in response.limitations)
