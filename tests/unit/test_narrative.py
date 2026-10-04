import json

import pytest

from backend.agents.narrative import check_numbers
from backend.llm.base import ProviderError
from backend.models.analysis import AskRequest, ExploratoryDraft, NarrativeDraft
from tests.helpers import draft, intent, result, run, service

REGIONS = [
    {"region": "Sul", "received_revenue": "1130867.83"},
    {"region": "Centro-Oeste", "received_revenue": "1101836.35"},
    {"region": "Nordeste", "received_revenue": "1079208.50"},
    {"region": "Norte", "received_revenue": "1042099.97"},
    {"region": "Sudeste", "received_revenue": "825090.13"},
]
COLUMNS = ["region", "received_revenue"]


def test_values_totals_shares_and_differences_are_verified():
    text = (
        "O Sul liderou com R$ 1.130.867,83 (21,8% do total de R$ 5,18 milhões), "
        "cerca de R$ 305,8 mil a mais que o Sudeste, que ficou 27,0% abaixo. "
        "A média foi de R$ 1.035.820,56 nas 5 regiões em 2026."
    )
    checked, unverified = check_numbers([text], REGIONS, COLUMNS, [])
    assert checked == 6 and unverified == []


def test_invented_numbers_are_reported():
    text = "A receita chegou a R$ 999.999,00 e cresceu 44% no Sul."
    checked, unverified = check_numbers([text], REGIONS, COLUMNS, [])
    assert checked == 2 and unverified == ["999.999,00", "44%"]


def test_percentages_returned_by_the_query_are_verified_by_magnitude():
    text = (
        "A diferença é de -10,48%. Isso significa que a receita do Sudeste ficou cerca de "
        "10,5% abaixo da região Sul."
    )
    assert check_numbers([text], [{"diff_percent": -10.48}], ["diff_percent"], []) == (2, [])
    assert check_numbers(["A diferença é de 11,71%."], [{"p": 11.71}], ["p"], []) == (1, [])


def test_differences_between_columns_of_a_row_are_verified():
    row = {"diff_percent": "11.71", "sul_revenue": "3599378.55", "sudeste_revenue": "3222070.32"}
    text = "O Sul ficou 11,7% acima do Sudeste, superando-o em cerca de R$ 377 mil."
    assert check_numbers([text], [row], list(row), []) == (2, [])
    assert check_numbers(["Superou em R$ 512 mil."], [row], list(row), []) == (1, ["512 mil"])


def test_fractions_ranges_and_numbers_from_the_question_are_not_false_alarms():
    rows = [{"age_group": g, "rate": r} for g, r in [(20, 0), (50, 0.57), (60, 0.73)]]
    text = "Pico de 73% no grupo de 60 a 69 anos; faixa 20-29 anos sem casos; 50 anos: 57%."
    assert check_numbers([text], rows, ["age_group", "rate"], [])[1] == []
    labels = [{"group": "55+", "rate": 46.77}]
    question = "Qual a taxa por sexo, separando quem tem 55 anos ou mais?"
    text = "Para quem tem 55 anos ou mais, 46,77%; o resto ficou em 61%."
    assert check_numbers([text], labels, ["group", "rate"], [question])[1] == ["61%"]


def test_negative_results_are_verified_by_magnitude():
    rows = [{"correlation": -0.404, "record_count": 642}]
    text = "Existe uma correlação moderada e negativa (-0,404), não de 0,52."
    assert check_numbers([text], rows, list(rows[0]), []) == (2, ["0,52"])


def test_short_million_and_billion_forms_are_scaled():
    rows = [
        {"category": "Livros", "revenue": "4581177.94"},
        {"category": "Casa", "revenue": "2929005.67"},
    ]
    text = "Livros soma R$ 4,58 mi e Casa R$ 2,93 mi; diferença de R$ 1,65 mi, não R$ 9,1 bi."
    assert check_numbers([text], rows, ["category", "revenue"], [])[1] == ["9,1 bi"]


def test_row_count_is_context_and_never_erases_digits_from_the_text():
    rows = [{"correlation": 0.1436, "product_count": 100}]
    text = "A correlação é fraca (0,14) entre os 1 produtos analisados; 642 linhas no total."
    checked, unverified = check_numbers(
        [text], rows, ["correlation", "product_count"], [], known_values=(1, 642)
    )
    assert checked == 1 and unverified == []


def test_percentages_that_match_nothing_are_still_reported():
    text = "A diferença é de -10,48%, mas o Norte cresceu 37%."
    assert check_numbers([text], [{"diff_percent": -10.48}], ["diff_percent"], []) == (
        2,
        ["37%"],
    )


def test_labels_dates_counts_and_years_are_not_treated_as_claims():
    rows = [
        {"product_name": "Produto 089", "total_units_sold": 572},
        {"product_name": "Produto 014", "total_units_sold": 571},
    ]
    text = "Em 01/09/2026, o Produto 089 vendeu 572 unidades; o top 2 inclui o Produto 014."
    checked, unverified = check_numbers([text], rows, ["product_name", "total_units_sold"], [])
    assert checked == 1 and unverified == []


def test_english_answers_are_read_in_the_us_number_format():
    text = (
        "The South led with R$ 1,130,867.83 (21.8% of the R$ 5.18 million total), about "
        "R$ 305.8 thousand above the Southeast; the average was 1,035,820.56 across 5 regions."
    )
    assert check_numbers([text], REGIONS, COLUMNS, [], locale="en-US") == (5, [])
    invented = "Revenue reached R$ 999,999.00, roughly 4.2 bn, up 44 percent."
    assert check_numbers([invented], REGIONS, COLUMNS, [], locale="en-US") == (
        3,
        ["999,999.00", "4.2 bn", "44 percent"],
    )
    rows = [{"age_group": 60, "rate": 0.73}]
    text = "73% in the 60 to 69 group."
    assert check_numbers([text], rows, list(rows[0]), [], locale="en-US") == (2, [])


# ---------- Narration inside the analysis flow ----------


def narrative(answer="Foram 70 clientes novos em setembro.", **updates):
    values = dict(
        answer=answer, highlights=["70 clientes novos."], caveats=[], follow_ups=["E em agosto?"]
    )
    return NarrativeDraft(**(values | updates))


def test_narration_uses_returned_rows_and_keeps_the_computed_answer():
    analyst, provider, _ = service(intent(), draft(), narrative(), narrative_enabled=True)
    response = run(analyst.ask(AskRequest(question="Clientes novos em setembro?")))
    assert response.status == "success" and "70" in response.answer
    assert response.narrative.answer == "Foram 70 clientes novos em setembro."
    assert response.narrative.follow_ups == ["E em agosto?"]
    assert response.narrative.rows_shared == 1 and response.narrative.unverified_numbers == []
    assert response.usage.llm_calls == 3
    payload = provider.payloads[2]
    assert payload["result"]["rows"] == [{"new_customers": 70}]
    assert payload["analysis"]["metric"] == {"name": "new_customers", "unit": "customers"}
    text = json.dumps(payload)
    assert "offline-db-secret" not in text and "SELECT" not in text


def test_the_chosen_language_reaches_every_model_call_and_the_number_check():
    english = narrative("There were 7,450 new customers.", highlights=[], follow_ups=[])
    analyst, provider, _ = service(intent(), draft(), english, narrative_enabled=True)
    response = run(analyst.ask(AskRequest(question="New customers in September?", language="en")))
    assert [payload.get("language") for payload in provider.payloads] == [
        "en-US",
        None,  # versioned metric SQL: no text for the user
        "en-US",
    ]
    assert response.narrative.unverified_numbers == ["7,450"]
    for payload, text in zip(provider.payloads, provider.instructions, strict=True):
        assert text.endswith("JSON in English.") == ("language" in payload)
    analyst, provider, _ = service(intent(), draft(), narrative(), narrative_enabled=True)
    run(analyst.ask(AskRequest(question="Clientes novos em setembro?", language="pt")))
    assert provider.payloads[0]["language"] == provider.payloads[2]["language"] == "pt-BR"
    assert AskRequest(question="Hi").language == "en"  # English unless asked otherwise


def test_narration_reports_numbers_absent_from_the_result():
    analyst, _, _ = service(
        intent(), draft(), narrative("Foram 7.450 clientes novos."), narrative_enabled=True
    )
    response = run(analyst.ask(AskRequest(question="Clientes novos em setembro?")))
    assert response.narrative.unverified_numbers == ["7.450"]


def test_only_the_configured_number_of_rows_is_shared():
    rows = [{"status": name, "orders": value} for name, value in (("paid", 3), ("pending", 2))]
    sql = "SELECT status, COUNT(id) AS orders FROM analytics.orders GROUP BY status ORDER BY status"
    analyst, provider, _ = service(
        intent(action="explore", metric=None, start_date=None, end_date=None),
        ExploratoryDraft(sql=sql, parameters=[], title="Pedidos por status", assumptions=[]),
        narrative("Lista parcial."),
        query_result=result(columns=["status", "orders"], rows=rows, row_count=2),
        narrative_enabled=True,
        narrative_max_rows=1,
    )
    response = run(analyst.ask(AskRequest(question="Clientes?")))
    assert provider.payloads[2]["result"]["rows"] == [{"status": "paid", "orders": 3}]
    assert provider.payloads[2]["result"]["partial"] is True
    assert provider.payloads[2]["analysis"]["title"] == "Pedidos por status"
    assert response.narrative.rows_shared == 1


@pytest.mark.parametrize(
    ("values", "settings", "note"),
    [
        ((ProviderError("provider_rate_limited", "Limite."),), {}, "provider_rate_limited"),
        ((), {"max_llm_calls": 2}, "call_budget_exceeded"),
        ((), {"narrative_enabled": False}, "desativada"),
    ],
)
def test_narration_failures_never_discard_the_computed_answer(values, settings, note):
    settings = {"narrative_enabled": True} | settings
    analyst, _, executor = service(intent(), draft(), *values, **settings)
    response = run(analyst.ask(AskRequest(question="Clientes novos em setembro?")))
    assert response.status == "success" and "70" in response.answer
    assert response.narrative is None and note in response.narrative_note
    executor.execute_async.assert_awaited_once()
