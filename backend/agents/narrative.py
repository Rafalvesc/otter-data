"""Deterministic support for model-written answers: bounded payloads and number checks."""

import re
from decimal import Decimal, InvalidOperation
from itertools import combinations

from backend.models.query import QueryResult

# pt-BR (1.234,56) or en-US (1,234.56), plain (1234.56 / 1234) and an optional scale word or
# percent sign. Both languages' words are accepted: a quoted label may use the other one.
SUFFIX = (
    r"(\s*(?:%|por cento|percent\b|mil\b|milh(?:ão|ões|oes|ao)\b|bilh(?:ão|ões|oes|ao)\b"
    r"|mi\b|bi\b|thousand\b|millions?\b|billions?\b|k\b|bn\b))?"
)
NUMBERS = {
    "pt-BR": re.compile(r"(?<![\w/])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)" + SUFFIX, re.I),
    "en-US": re.compile(r"(?<![\w/])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)" + SUFFIX, re.I),
}
NUMBER = NUMBERS["pt-BR"]
# "60 a 69", "60-69", "20–29 anos": the end of a range whose start is a known value is a label.
RANGE = re.compile(r"(?<![\w,.])(\d{1,4})\s*(?:-|–|a|até|to)\s*(\d{1,4})(?![\w,.])")
DATE_TEXT = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}(?:T[\d:.+-]+)?\b")
# Longest prefix first: "milhões" and "million" also start with "mil".
SCALES = {
    "million": Decimal(10) ** 6,
    "billion": Decimal(10) ** 9,
    "thousand": Decimal(1000),
    "milh": Decimal(10) ** 6,
    "bilh": Decimal(10) ** 9,
    "mil": Decimal(1000),
}
SHORT_SCALES = {
    "mi": Decimal(10) ** 6,
    "bi": Decimal(10) ** 9,
    "k": Decimal(1000),
    "bn": Decimal(10) ** 9,
}
PERCENT_WORDS = ("%", "por cento", "percent")
MAX_PAIRWISE_ROWS = 60
MAX_ROW_CELLS = 12


def to_decimal(value) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def shared_rows(query: QueryResult, limit: int) -> list[dict]:
    return [dict(row) for row in query.rows[:limit]]


def reference_values(rows: list[dict], columns: list[str]) -> tuple[set[Decimal], set[Decimal]]:
    """Values a faithful answer may cite, plus percentages derivable from them."""
    values: set[Decimal] = set()
    percents: set[Decimal] = set()
    for column in columns:
        numbers = [n for n in (to_decimal(row.get(column)) for row in rows) if n is not None]
        if not numbers:
            continue
        total = sum(numbers)
        values.update(numbers)
        values.update({total, total / len(numbers), max(numbers) - min(numbers)})
        if total:
            percents.update(number / total * 100 for number in numbers)
        if len(numbers) <= MAX_PAIRWISE_ROWS:
            for a, b in combinations(numbers, 2):
                values.add(abs(a - b))
                for x, y in ((a, b), (b, a)):
                    if y:
                        percents.add((x / y - 1) * 100)
                        percents.add(abs(x / y - 1) * 100)
                        percents.add(x / y * 100)
    # Side-by-side columns of one row (e.g. sul_revenue and sudeste_revenue) are compared too.
    if len(rows) <= MAX_PAIRWISE_ROWS:
        for row in rows:
            cells = [to_decimal(row.get(column)) for column in columns]
            cells = [cell for cell in cells if cell is not None]
            for a, b in combinations(cells[:MAX_ROW_CELLS], 2):
                values.update({abs(a - b), a + b})
                for x, y in ((a, b), (b, a)):
                    if y:
                        percents.add((x / y - 1) * 100)
                        percents.add(x / y * 100)
    return values, percents


def _tolerance(raw: str, scale: Decimal, reference: Decimal, locale: str = "pt-BR") -> Decimal:
    point = "." if locale == "en-US" else ","
    decimals = len(raw.split(point)[-1]) if point in raw else 0
    if (
        locale != "en-US"
        and "," not in raw
        and "." in raw
        and not re.fullmatch(r"\d{1,3}(\.\d{3})+", raw)
    ):
        decimals = len(raw.split(".")[-1])
    precision = Decimal(1).scaleb(-decimals) / 2 * scale
    return max(precision, abs(reference) * Decimal("0.002"))


def parse_number(raw: str, locale: str = "pt-BR") -> Decimal | None:
    if locale == "en-US":
        raw = raw.replace(",", "")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", raw):
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", ".")
    return to_decimal(raw)


def check_numbers(
    texts: list[str],
    rows: list[dict],
    columns: list[str],
    ignore: list[str],
    known_values: tuple = (),
    locale: str = "pt-BR",
):
    """Return (checked, unverified) for numbers mentioned in the model's text.

    `ignore` holds texts (question, date) whose exact wording is removed before checking;
    `known_values` holds numbers that are context, not claims (e.g. the result's row count);
    `locale` is the number format the answer was asked to use (pt-BR or en-US)."""
    pattern = NUMBERS.get(locale, NUMBER)
    values, percents = reference_values(rows, columns)
    text = " ".join(texts)
    # Labels (product names, regions, dates) and question text may legitimately contain digits.
    labels = {str(value) for row in rows for value in row.values() if to_decimal(value) is None}
    for label in sorted(labels | set(ignore), key=len, reverse=True):
        if label and any(character.isdigit() for character in label):
            text = text.replace(label, " ")
    text = DATE_TEXT.sub(" ", text)
    # Numbers already given by the question or by labels ("55 anos ou mais", "55+") are context,
    # not claims about the result.
    known = {
        number
        for source in [*ignore, *labels]
        for number in (parse_number(m.group(1), locale) for m in pattern.finditer(str(source)))
        if number is not None
    }
    known.update(Decimal(str(value)) for value in known_values)

    def range_end(match: re.Match) -> str:
        start, end = Decimal(match.group(1)), Decimal(match.group(2))
        return (
            match.group(1)
            if end > start and (start in values or start in known)
            else match.group(0)
        )

    text = RANGE.sub(range_end, text)
    checked, unverified = 0, []
    limit = max(10, len(rows))
    for match in pattern.finditer(text):
        raw, suffix = match.group(1), (match.group(2) or "").strip().lower()
        number = parse_number(raw, locale)
        if number is None:
            continue
        is_percent = suffix in PERCENT_WORDS
        # Short forms used in charts and answers ("R$ 4,58 mi", "$4.6 bn", "12k").
        scale = SHORT_SCALES.get(suffix) or next(
            (factor for key, factor in SCALES.items() if suffix.startswith(key)), Decimal(1)
        )
        plain_integer = not suffix and number == number.to_integral_value()
        if plain_integer and (number <= limit or 1900 <= number <= 2100):
            continue  # counts like "5 produtos" and years
        if not suffix and number in known:
            continue
        checked += 1
        target = number * scale
        if is_percent:
            # A column may already hold a percentage, and a sign is often said in words
            # ("10,5% abaixo" for -10,48), so percentages are compared by magnitude.
            # Rates returned as fractions (0,73) are cited as percentages (73%).
            candidates = {abs(c) for c in percents | values}
            candidates |= {abs(c) * 100 for c in values if abs(c) <= 1}
        else:
            # The pattern reads digits only, so "-0,404" arrives as 0,404: compare magnitudes.
            candidates = values | {abs(c) for c in values}
        if not any(abs(target - c) <= _tolerance(raw, scale, c, locale) for c in candidates):
            unverified.append(match.group(0).strip())
    return checked, list(dict.fromkeys(unverified))
