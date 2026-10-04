"""Generic, data-free hints for a database error, used to let the model rewrite a failed query.

Driver messages may quote values from the base, so they never reach the model or the logs. Only
the error class (SQLSTATE, MySQL error number or DuckDB exception type) is mapped to fixed text.
"""

AGGREGATION = (
    "Erro de agregação: não aninhe funções de agregação (ex.: CORR(SUM(...))) e agrupe todas as "
    "colunas não agregadas; calcule a primeira agregação numa subconsulta e aplique a segunda na "
    "consulta externa."
)
FUNCTION = (
    "Função ou combinação de tipos inexistente neste banco; converta os argumentos com CAST, "
    "inclusive parâmetros (ex.: CAST(:start_date AS DATE), CAST(x AS NUMERIC)), ou use outra "
    "função permitida."
)
TYPES = "Tipos incompatíveis na expressão; converta explicitamente com CAST."
DIVISION = "Divisão por zero: proteja o divisor com NULLIF(divisor, 0)."
FORMAT = "Valor em formato inválido para o tipo (data ou número); confira conversões e parâmetros."
SCALAR = "Uma subconsulta escalar retornou mais de uma linha; agregue ou restrinja a subconsulta."

POSTGRES = {
    "42803": AGGREGATION,  # grouping_error
    "42883": FUNCTION,  # undefined_function
    "42804": TYPES,  # datatype_mismatch
    "42846": TYPES,  # cannot_coerce
    "22012": DIVISION,  # division_by_zero
    "22P02": FORMAT,  # invalid_text_representation
    "22007": FORMAT,  # invalid_datetime_format
    "22008": FORMAT,  # datetime_field_overflow
    "21000": SCALAR,  # cardinality_violation
}
MYSQL = {
    1111: AGGREGATION,  # ER_INVALID_GROUP_FUNC_USE
    1055: AGGREGATION,  # ER_WRONG_FIELD_WITH_GROUP
    1140: AGGREGATION,  # ER_MIX_OF_GROUP_FUNC_AND_FIELDS
    1305: FUNCTION,  # ER_SP_DOES_NOT_EXIST
    1582: FUNCTION,  # ER_WRONG_PARAMCOUNT_TO_NATIVE_FCT
    1365: DIVISION,  # ER_DIVISION_BY_ZERO
    1292: FORMAT,  # ER_TRUNCATED_WRONG_VALUE
    1242: SCALAR,  # ER_SUBQUERY_NO_1_ROW
}
DUCKDB = {
    "BinderException": f"{FUNCTION} Ou: {AGGREGATION}",
    "ConversionException": FORMAT,
    "InvalidInputException": FORMAT,
    "OutOfRangeException": FORMAT,
}


def postgres_hint(error: Exception) -> str | None:
    return POSTGRES.get(getattr(error, "sqlstate", None) or "")


def mysql_hint(error: Exception) -> str | None:
    number = error.args[0] if getattr(error, "args", None) else None
    return MYSQL.get(number) if isinstance(number, int) else None


def duckdb_hint(error: Exception) -> str | None:
    return DUCKDB.get(type(error).__name__)
