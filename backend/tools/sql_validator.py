"""Fail-closed validation of a deliberately small PostgreSQL SELECT subset."""

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from importlib.resources import files
from typing import Any

import sqlglot
import yaml
from sqlglot import ErrorLevel, exp
from sqlglot.dialects.dialect import Dialect
from sqlglot.errors import OptimizeError, ParseError, TokenError, UnsupportedError
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, traverse_scope

from backend.models.query import QueryCode, ValidationResult

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]{0,62}\Z")
# sqlglot names the unresolved column; only identifiers the model itself wrote, never data.
UNRESOLVED = re.compile(
    r"Column '([A-Za-z_0-9]{1,63})' could not be resolved(?: for table: '([A-Za-z_0-9]{1,63})')?"
)
SENSITIVE_NAMES = frozenset({"email", "phone", "cpf", "tax_id"})
FUNCTION_NODES = frozenset(
    {
        "Count",
        "Sum",
        "Avg",
        "Min",
        "Max",
        "Abs",
        "Round",
        "Coalesce",
        "Nullif",
        "TimestampTrunc",
        "Cast",
        "Case",
        "If",
    }
)
STRUCTURAL_NODES = frozenset(
    {
        "Select",
        "From",
        "Where",
        "Group",
        "Having",
        "Order",
        "Ordered",
        "Limit",
        "Offset",
        "Distinct",
        "With",
        "CTE",
        "Subquery",
        "Table",
        "TableAlias",
        "Column",
        "Identifier",
        "Alias",
        "Literal",
        "Null",
        "Boolean",
        "Star",
        "Placeholder",
        "Paren",
        "And",
        "Or",
        "Not",
        "EQ",
        "NEQ",
        "GT",
        "GTE",
        "LT",
        "LTE",
        "Is",
        "In",
        "Between",
        "Add",
        "Sub",
        "Mul",
        "Div",
        "Neg",
        "Like",
        "ILike",
        "Join",
        "DataType",
        "DataTypeParam",
        "AtTimeZone",
        "Var",
    }
)
# Pure date/text helpers needed by MySQL and DuckDB dialects (and EXTRACT in PostgreSQL).
DATE_FUNCTION_NODES = frozenset(
    {
        "Extract",
        "Year",
        "Month",
        "Day",
        "Quarter",
        "DateTrunc",
        "TimeToStr",
        "TsOrDsToDate",
        "TsOrDsToTimestamp",
        "Lower",
        "Upper",
    }
)
# Read-only statistics: dispersion, percentiles and simple math used for outliers and distributions.
# LN/EXP stay out (domain errors and overflow); unknown (Anonymous) functions are always rejected.
STAT_FUNCTION_NODES = frozenset(
    {
        "Stddev",
        "StddevPop",
        "StddevSamp",
        "Variance",
        "VariancePop",
        "Sqrt",
        "Pow",
        "Floor",
        "Ceil",
        "Mod",
        "Greatest",
        "Least",
        "PercentileCont",
        "PercentileDisc",
        "WithinGroup",
        "Median",
        "Mode",
        "Filter",
        "Corr",
        "CovarSamp",
        "CovarPop",
    }
)
# Window functions (OVER ...): read-only rankings, running totals and per-row comparisons.
WINDOW_NODES = frozenset(
    {
        "Window",
        "WindowSpec",
        "RowNumber",
        "Rank",
        "DenseRank",
        "Ntile",
        "PercentRank",
        "CumeDist",
        "Lag",
        "Lead",
    }
)
ALLOWED_NODES = (
    STRUCTURAL_NODES | FUNCTION_NODES | DATE_FUNCTION_NODES | STAT_FUNCTION_NODES | WINDOW_NODES
)
UNIT_PARENTS = (exp.TimestampTrunc, exp.DateTrunc, exp.Extract)
DIALECTS = frozenset({"postgres", "mysql", "duckdb"})
CAST_TYPES = frozenset(
    {
        "INT",
        "BIGINT",
        "SMALLINT",
        "DECIMAL",
        "DOUBLE",
        "FLOAT",
        "TEXT",
        "VARCHAR",
        "DATE",
        "TIMESTAMP",
        "TIMESTAMPTZ",
        "BOOLEAN",
    }
)
DATE_UNITS = frozenset({"YEAR", "QUARTER", "MONTH", "WEEK", "DAY", "HOUR", "MINUTE"})
TIMEZONES = frozenset({"America/Sao_Paulo", "UTC"})


def numeric_round(tree: exp.Expression) -> None:
    """PostgreSQL has ROUND(numeric, int) only: ROUND(AVG(...)/CORR(...), 2) on double precision
    fails at run time. Casting the rounded value to NUMERIC keeps the meaning and runs."""
    for node in list(tree.find_all(exp.Round)):
        if node.args.get("decimals") is not None and not isinstance(node.this, exp.Cast):
            node.this.replace(exp.Cast(this=node.this.copy(), to=exp.DataType.build("DECIMAL")))


def nested_aggregate(tree: exp.Expression) -> bool:
    """An aggregate directly inside another (CORR(SUM(x), ...)) is invalid SQL. Window functions
    over aggregates (SUM(SUM(x)) OVER ()) and aggregates inside a subquery are fine."""
    for outer in tree.find_all(exp.AggFunc):
        if isinstance(outer.parent, exp.Window):
            continue
        for inner in outer.find_all(exp.AggFunc):
            if inner is outer:
                continue
            node, crosses_query = inner.parent, False
            while node is not None and node is not outer:
                if isinstance(node, (exp.Select, exp.Window)):
                    crosses_query = True
                    break
                node = node.parent
            if not crosses_query:
                return True
    return False


def unlabeled_groups(tree: exp.Expression) -> None:
    """The answer's rows must say which group they belong to: a top-level GROUP BY column that
    is not selected returns bare numbers ("1594, 234, 172" with no status). Subqueries may group
    without selecting the key (e.g. counts per customer that the outer query averages)."""
    group = tree.args.get("group")
    if group is None:
        return
    selected = {
        (column.table, column.name)
        for expression in tree.expressions
        for column in expression.find_all(exp.Column)
    }
    missing = [
        key.name
        for key in group.expressions
        if isinstance(key, exp.Column) and (key.table, key.name) not in selected
    ]
    if missing:
        raise RejectedSQL(
            QueryCode.UNSUPPORTED_SQL,
            f"Inclua no SELECT as colunas do GROUP BY ({', '.join(missing)}), para que cada "
            "linha do resultado diga a que grupo pertence.",
        )


def unresolved_message(error: Exception) -> str:
    found = UNRESOLVED.search(str(error))
    if not found:
        return "Colunas ou aliases não puderam ser resolvidos no catálogo autorizado."
    column, table = found.groups()
    where = f" em {table}" if table else ""
    return (
        f"A coluna {column} não existe{where} neste ponto da consulta. Na consulta externa, use "
        "os nomes de saída da subconsulta, não os aliases de tabelas internas."
    )


class RejectedSQL(Exception):
    """A policy rejection. `repairable` says whether the model may get one chance to rewrite it:
    false for writes, multiple statements and sensitive fields, which end the request."""

    def __init__(self, code: QueryCode, message: str, *, repairable: bool = True):
        self.code = code
        self.message = message
        self.repairable = repairable
        super().__init__(message)


@dataclass(frozen=True)
class PreparedQuery:
    validation: ValidationResult
    parameter_values: tuple[Any, ...]


def render_bound(
    tree: exp.Expression, dialect: str, parameter_names: tuple[str, ...]
) -> tuple[str, tuple[str, ...]]:
    """Render SQL with driver placeholders; returns the parameter order the driver expects.

    PostgreSQL (psycopg raw cursors) and DuckDB bind numbered $n, so percent signs stay literal.
    PyMySQL binds positional %s through %-formatting, so literal percent signs are doubled.
    """
    dialect_instance = Dialect.get_or_raise(dialect)
    positional = dialect == "mysql"
    positions = {name: index for index, name in enumerate(parameter_names, start=1)}
    order: list[str] = []

    class BoundGenerator(type(dialect_instance).Generator):
        def placeholder_sql(self, expression: exp.Placeholder) -> str:
            if positional:
                order.append(expression.name)
                return f"__otter_param_{len(order)}__"
            return f"${positions[expression.name]}"

    sql = BoundGenerator(
        dialect=dialect_instance, comments=False, unsupported_level=ErrorLevel.RAISE
    ).generate(tree)
    if not positional:
        return sql, parameter_names
    sql = sql.replace("%", "%%")
    for index in range(len(order), 0, -1):
        sql = sql.replace(f"__otter_param_{index}__", "%s")
    return sql, tuple(order)


def safe_type(value: Any, dialect: str) -> str:
    """Column types come from introspection; unknown names must not break qualification."""
    try:
        return exp.DataType.build(str(value), dialect=dialect).sql(dialect=dialect)
    except Exception:  # noqa: BLE001 - any unparsable type degrades to TEXT
        return "TEXT"


class SQLValidator:
    """Validates one SELECT against an approved catalog.

    Defaults to the bundled analytics catalog (PostgreSQL schema `analytics`). Connected sources
    pass their introspected catalog, the schema/database every table must be qualified with, and
    the SQL dialect.
    """

    def __init__(
        self,
        tables: dict[str, dict] | None = None,
        *,
        schema: str = "analytics",
        dialect: str = "postgres",
    ):
        if dialect not in DIALECTS:
            raise ValueError(f"Dialeto não suportado: {dialect}")
        if tables is None:
            tables = yaml.safe_load(
                files("backend").joinpath("semantic/schema.yaml").read_text(encoding="utf-8")
            )["tables"]
        self._schema = schema
        self._dialect = dialect
        self._columns = {
            table: {column: safe_type(kind, dialect) for column, kind in spec["columns"].items()}
            for table, spec in tables.items()
        }
        # (child table, foreign key column) -> (parent table, key column)
        self._foreign_keys = {
            (table, column): tuple(target.split("."))
            for table, spec in tables.items()
            for column, target in spec.get("relationships", {}).items()
        }
        self._relationships = frozenset(
            frozenset((child, parent)) for child, parent in self._foreign_keys.items()
        )

    @property
    def dialect(self) -> str:
        return self._dialect

    def validate(self, sql: str, parameters: dict[str, Any] | None = None) -> ValidationResult:
        return self.prepare(sql, parameters).validation

    def prepare(self, sql: str, parameters: dict[str, Any] | None = None) -> PreparedQuery:
        try:
            return self._prepare(sql, parameters)
        except RejectedSQL as rejection:
            return PreparedQuery(
                ValidationResult(
                    allowed=False,
                    code=rejection.code,
                    message=rejection.message,
                    repairable=rejection.repairable,
                ),
                (),
            )
        except (ParseError, TokenError, RecursionError):
            return PreparedQuery(
                ValidationResult(
                    allowed=False,
                    code=QueryCode.INVALID_SQL,
                    message="SQL inválido ou não suportado pelo parser.",
                    repairable=True,
                ),
                (),
            )
        except OptimizeError as error:
            return PreparedQuery(
                ValidationResult(
                    allowed=False,
                    code=QueryCode.COLUMN_NOT_ALLOWED,
                    message=unresolved_message(error),
                    repairable=True,
                ),
                (),
            )
        except (UnsupportedError, ValueError, TypeError, KeyError):
            return PreparedQuery(
                ValidationResult(
                    allowed=False,
                    code=QueryCode.UNSUPPORTED_SQL,
                    message="Forma SQL não suportada pela política atual.",
                    repairable=True,
                ),
                (),
            )

    def _prepare(self, sql: str, parameters: dict[str, Any] | None) -> PreparedQuery:
        if not isinstance(sql, str) or not sql.strip():
            raise RejectedSQL(QueryCode.INVALID_SQL, "Informe uma consulta SQL não vazia.")
        if len(sql) > 16000:
            raise RejectedSQL(QueryCode.COMPLEXITY_LIMIT, "SQL excede o limite de tamanho.")
        statements = sqlglot.parse(sql, read=self._dialect, error_level=ErrorLevel.RAISE)
        if len(statements) != 1 or statements[0] is None:
            raise RejectedSQL(
                QueryCode.MULTIPLE_STATEMENTS, "Permita exatamente uma instrução.", repairable=False
            )
        tree = normalize_identifiers(statements[0], dialect=self._dialect)
        if isinstance(tree, exp.SetOperation):
            # Still outside the policy, but a read: the model gets one chance to rewrite it.
            raise RejectedSQL(
                QueryCode.UNSUPPORTED_SQL,
                "UNION, INTERSECT e EXCEPT não são permitidos. Traga os valores como colunas "
                "lado a lado num único SELECT (ex.: SUM(CASE WHEN ... THEN 1 ELSE 0 END) por "
                "coluna) ou agrupe com GROUP BY.",
            )
        if not isinstance(tree, exp.Select):
            raise RejectedSQL(
                QueryCode.READ_ONLY_REQUIRED, "Apenas SELECT é permitido.", repairable=False
            )
        for join in tree.find_all(exp.Join):
            if not join.args.get("on") and not join.args.get("using"):
                raise RejectedSQL(
                    QueryCode.JOIN_NOT_ALLOWED,
                    "Junção por vírgula ou CROSS JOIN não é permitida. Para comparar grupos, "
                    "agregue numa única subconsulta com GROUP BY e compare na consulta externa "
                    "com MAX(CASE WHEN ... THEN ... END).",
                )
        nodes = list(tree.walk())
        if len(nodes) > 500 or any(node.depth > 32 for node in nodes):
            raise RejectedSQL(QueryCode.COMPLEXITY_LIMIT, "SQL excede a complexidade permitida.")
        selects, joins = len(list(tree.find_all(exp.Select))), len(list(tree.find_all(exp.Join)))
        if selects > 8 or joins > 6:
            raise RejectedSQL(
                QueryCode.COMPLEXITY_LIMIT,
                f"Consulta grande demais ({selects} SELECTs, {joins} joins; máximo 8 e 6). "
                "Simplifique: faça os joins uma vez só e agregue com GROUP BY.",
            )
        self._qualify_catalog_tables(tree)
        self._check_nodes(tree)
        if nested_aggregate(tree):
            raise RejectedSQL(
                QueryCode.UNSUPPORTED_SQL,
                "Agregações aninhadas (ex.: CORR(SUM(...)) ou AVG(COUNT(...))) não são permitidas: "
                "calcule a primeira agregação numa subconsulta com GROUP BY e aplique a segunda "
                "na consulta externa.",
            )
        self._check_relations(tree)
        parameter_names, supplied = self._check_parameters(tree, parameters)
        qualified = qualify(
            tree,
            dialect=self._dialect,
            schema={self._schema: self._columns},
            expand_stars=False,
            infer_schema=False,
            allow_partial_qualification=False,
            validate_qualify_columns=True,
        )
        self._check_nodes(qualified)
        sources = self._check_relations(qualified)
        self._check_joins(qualified)
        self._check_fan_out(qualified)
        unlabeled_groups(qualified)
        names = qualified.named_selects
        if not names or len(names) != len(set(names)):
            raise RejectedSQL(QueryCode.COLUMN_NOT_ALLOWED, "Use nomes de saída distintos.")
        if self._dialect == "postgres":
            numeric_round(qualified)
        rendered, order = render_bound(qualified, self._dialect, parameter_names)
        values = tuple(supplied[name] for name in order)
        fields = self._catalog_fields(qualified)
        return PreparedQuery(
            ValidationResult(
                allowed=True,
                code=QueryCode.OK,
                message="Consulta aprovada.",
                normalized_sql=rendered,
                sources=tuple(sorted(sources)),
                parameter_names=parameter_names,
                fields=fields,
            ),
            values,
        )

    def _qualify_catalog_tables(self, tree: exp.Expression) -> None:
        """`FROM orders` means the approved `<schema>.orders` when orders is a catalog table.

        The executed SQL names the schema explicitly; any other unqualified name (unknown tables,
        system views) is left as written and rejected by `_check_relations`."""
        ctes = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
        for table in tree.find_all(exp.Table):
            if (
                not table.args.get("db")
                and not table.args.get("catalog")
                and table.name in self._columns
                and table.name not in ctes
            ):
                table.set("db", exp.to_identifier(self._schema))

    def _catalog_fields(self, tree: exp.Expression) -> tuple[str, ...]:
        """Approved catalog columns the query reads, as schema.table.column."""
        fields = set()
        for scope in traverse_scope(tree):
            for column in scope.columns:
                source = scope.sources.get(column.table)
                if isinstance(source, exp.Table) and column.name in self._columns.get(
                    source.name, {}
                ):
                    fields.add(f"{self._schema}.{source.name}.{column.name}")
        return tuple(sorted(fields))

    def _check_nodes(self, tree: exp.Expression) -> None:
        for node in tree.walk():
            name = type(node).__name__
            if name in {"Insert", "Update", "Delete", "Into", "Lock"}:
                raise RejectedSQL(
                    QueryCode.READ_ONLY_REQUIRED,
                    "Escrita e bloqueios são proibidos.",
                    repairable=False,
                )
            if isinstance(node, exp.Func) and name not in ALLOWED_NODES:
                label = node.name if isinstance(node, exp.Anonymous) else node.sql_name()
                raise RejectedSQL(
                    QueryCode.FUNCTION_NOT_ALLOWED,
                    f"Função {label.upper()[:40]} não permitida; use só as funções autorizadas.",
                )
            if name not in ALLOWED_NODES:
                raise RejectedSQL(QueryCode.UNSUPPORTED_SQL, "Construção SQL não autorizada.")
            if isinstance(node, exp.Identifier) and not IDENTIFIER.fullmatch(node.name):
                raise RejectedSQL(QueryCode.UNSUPPORTED_SQL, "Identificador não suportado.")
            if isinstance(node, exp.Column) and node.name.lower() in SENSITIVE_NAMES:
                raise RejectedSQL(
                    QueryCode.COLUMN_NOT_ALLOWED, "Campo sensível bloqueado.", repairable=False
                )
            if isinstance(node, exp.Star) and not (
                isinstance(node.parent, exp.Count)
                and node.parent.this is node
                and not any(node.args.values())
            ):
                raise RejectedSQL(
                    QueryCode.WILDCARD_NOT_ALLOWED, "Liste as colunas explicitamente."
                )
            if isinstance(node, exp.With) and node.args.get("recursive"):
                raise RejectedSQL(QueryCode.UNSUPPORTED_SQL, "CTEs recursivas não são permitidas.")
            if isinstance(node, exp.Select) and len(node.expressions) > 50:
                raise RejectedSQL(QueryCode.COMPLEXITY_LIMIT, "Colunas de saída em excesso.")
            if isinstance(node, exp.Literal) and len(node.this) > 2048:
                raise RejectedSQL(QueryCode.COMPLEXITY_LIMIT, "Literal excede o limite de tamanho.")
            if isinstance(node, exp.DataType) and node.this.value not in CAST_TYPES:
                raise RejectedSQL(QueryCode.UNSUPPORTED_SQL, "Tipo de cast não autorizado.")
            if isinstance(node, exp.DataTypeParam):
                if not isinstance(node.this, exp.Literal) or not node.this.is_int:
                    raise RejectedSQL(QueryCode.UNSUPPORTED_SQL, "Precisão de cast inválida.")
                if not 0 <= int(node.this.this) <= 38:
                    raise RejectedSQL(QueryCode.COMPLEXITY_LIMIT, "Precisão de cast excessiva.")
            if isinstance(node, exp.Var) and not (
                isinstance(node.parent, UNIT_PARENTS) and node.name.upper() in DATE_UNITS
            ):
                raise RejectedSQL(QueryCode.UNSUPPORTED_SQL, "Unidade temporal não autorizada.")
            if isinstance(node, exp.AtTimeZone) and not (
                isinstance(node.args.get("zone"), exp.Literal)
                and node.args["zone"].this in TIMEZONES
            ):
                raise RejectedSQL(QueryCode.UNSUPPORTED_SQL, "Fuso horário não autorizado.")
            if isinstance(node, exp.TableAlias) and node.args.get("columns"):
                raise RejectedSQL(
                    QueryCode.UNSUPPORTED_SQL, "Aliases de listas de colunas não suportados."
                )

    def _check_relations(self, tree: exp.Expression) -> set[str]:
        sources = set()
        for scope in traverse_scope(tree):
            for _, (_, source) in scope.selected_sources.items():
                if isinstance(source, Scope):
                    continue
                if not isinstance(source, exp.Table) or not isinstance(source.this, exp.Identifier):
                    raise RejectedSQL(QueryCode.RELATION_NOT_ALLOWED, "Fonte não autorizada.")
                if source.catalog or source.db != self._schema or source.name not in self._columns:
                    raise RejectedSQL(
                        QueryCode.RELATION_NOT_ALLOWED,
                        "Use somente tabelas aprovadas, qualificadas como "
                        f"{self._schema}.<tabela>.",
                    )
                sources.add(f"{self._schema}.{source.name}")
        if not sources:
            raise RejectedSQL(
                QueryCode.RELATION_NOT_ALLOWED, "A consulta deve usar uma view aprovada."
            )
        return sources

    def _check_joins(self, tree: exp.Expression) -> None:
        for scope in traverse_scope(tree):
            for join in scope.expression.args.get("joins", []):
                condition = join.args.get("on")
                if (
                    join.args.get("method")
                    or join.args.get("using")
                    or join.args.get("kind") not in (None, "", "INNER")
                    or join.args.get("side") not in (None, "", "LEFT", "RIGHT", "FULL")
                    or condition is None
                    or not isinstance(join.this, exp.Table)
                ):
                    raise RejectedSQL(
                        QueryCode.JOIN_NOT_ALLOWED, "Join sem relação explícita autorizada."
                    )
                predicates = (
                    list(condition.flatten()) if isinstance(condition, exp.And) else [condition]
                )
                for predicate in predicates:
                    if not isinstance(predicate, exp.EQ) or not all(
                        isinstance(operand, exp.Column)
                        for operand in (predicate.this, predicate.expression)
                    ):
                        raise RejectedSQL(
                            QueryCode.JOIN_NOT_ALLOWED, "Join deve comparar chaves documentadas."
                        )
                    left, right = predicate.this, predicate.expression
                    a, b = scope.sources.get(left.table), scope.sources.get(right.table)
                    if not isinstance(a, exp.Table) or not isinstance(b, exp.Table):
                        raise RejectedSQL(
                            QueryCode.JOIN_NOT_ALLOWED, "Join em fonte derivada não suportado."
                        )
                    relationship = frozenset(((a.name, left.name), (b.name, right.name)))
                    if left.table == right.table or join.this.alias_or_name not in (
                        left.table,
                        right.table,
                    ):
                        raise RejectedSQL(
                            QueryCode.JOIN_NOT_ALLOWED, "Join não conecta a fonte adicionada."
                        )
                    if relationship not in self._relationships:
                        raise RejectedSQL(
                            QueryCode.JOIN_NOT_ALLOWED, "Relacionamento fora do catálogo."
                        )

    def _check_fan_out(self, tree: exp.Expression) -> None:
        """Reject SUM, AVG and COUNT(column) over a table whose rows the joins repeat.

        Following a foreign key from child to parent keeps one row per child row; going from a
        parent to a child (orders -> order_items) repeats the parent's rows once per child. A
        measure taken from a table reached that way is counted several times (a payment summed
        once per item of its order), so the query is refused with a way to rewrite it."""
        for scope in traverse_scope(tree):
            joins = scope.expression.args.get("joins") or []
            if not joins:
                continue
            names = {
                alias: source.name
                for alias, source in scope.sources.items()
                if isinstance(source, exp.Table)
            }
            neighbours: dict[str, set[str]] = {alias: set() for alias in names}
            children: dict[str, set[str]] = {alias: set() for alias in names}
            for join in joins:
                condition = join.args["on"]
                predicates = (
                    list(condition.flatten()) if isinstance(condition, exp.And) else [condition]
                )
                for predicate in predicates:
                    for child, parent in (
                        (predicate.this, predicate.expression),
                        (predicate.expression, predicate.this),
                    ):
                        key = (names[child.table], child.name)
                        if self._foreign_keys.get(key) == (names[parent.table], parent.name):
                            neighbours[child.table].add(parent.table)
                            neighbours[parent.table].add(child.table)
                            children[parent.table].add(child.table)
            for aggregate in scope.expression.find_all(exp.Sum, exp.Avg, exp.Count):
                if (
                    aggregate.find_ancestor(exp.Select) is not scope.expression
                    or isinstance(aggregate.parent, exp.Window)
                    or aggregate.find(exp.Distinct)
                    or aggregate.find(exp.Star)
                ):
                    continue
                for column in aggregate.find_all(exp.Column):
                    if column.table not in names:
                        continue
                    repeating = self._repeating_join(column.table, neighbours, children)
                    if repeating:
                        parent, child = (names[alias] for alias in repeating)
                        raise RejectedSQL(
                            QueryCode.DUPLICATED_AGGREGATE,
                            f"{aggregate.key.upper()} de {names[column.table]}.{column.name} "
                            f"contaria valores repetidos: o join com {child} traz várias linhas "
                            f"para cada linha de {parent}. Use a medida da tabela mais detalhada, "
                            "COUNT(DISTINCT ...) para contar, ou filtre com IN (SELECT ...) em "
                            "vez de juntar (ex.: WHERE x.order_id IN (SELECT order_id FROM ... "
                            "WHERE ...)).",
                        )

    @staticmethod
    def _repeating_join(start: str, neighbours: dict, children: dict) -> tuple[str, str] | None:
        """The first (parent, child) join reached from `start` in the parent-to-child direction."""
        seen, stack = {start}, [start]
        while stack:
            node = stack.pop()
            for other in neighbours[node]:
                if other in seen:
                    continue
                if other in children[node]:
                    return node, other
                seen.add(other)
                stack.append(other)
        return None

    @staticmethod
    def _check_parameters(tree: exp.Expression, parameters: dict[str, Any] | None):
        names = tuple(dict.fromkeys(node.name for node in tree.find_all(exp.Placeholder)))
        supplied = {} if parameters is None else parameters
        if not isinstance(supplied, dict):
            raise RejectedSQL(QueryCode.INVALID_PARAMETERS, "Parâmetros ausentes ou excedentes.")
        if set(supplied) != set(names):
            # Only the names the model wrote itself, never values, so a rewrite can fix them.
            missing = [
                name for name in names if name not in supplied and IDENTIFIER.fullmatch(name)
            ]
            extra = [name for name in supplied if name not in names and IDENTIFIER.fullmatch(name)]
            detail = "".join(
                f" {label}: {', '.join(':' + name for name in items)}."
                for label, items in (("Sem valor", missing), ("Não usados no SQL", extra))
                if items
            )
            raise RejectedSQL(
                QueryCode.INVALID_PARAMETERS,
                "Parâmetros ausentes ou excedentes."
                + detail
                + " Cada :nome do SQL precisa de um valor em parameters, com o mesmo nome.",
            )
        if not all(IDENTIFIER.fullmatch(name) for name in names):
            raise RejectedSQL(
                QueryCode.INVALID_PARAMETERS, "Use parâmetros nomeados como :start_date."
            )
        for value in supplied.values():
            if value is not None and type(value) not in (
                str,
                int,
                float,
                bool,
                Decimal,
                date,
                datetime,
            ):
                raise RejectedSQL(QueryCode.INVALID_PARAMETERS, "Tipo de parâmetro não suportado.")
            if isinstance(value, str) and len(value) > 2048:
                raise RejectedSQL(
                    QueryCode.INVALID_PARAMETERS, "Parâmetro excede o limite de tamanho."
                )
            if isinstance(value, float) and not math.isfinite(value):
                raise RejectedSQL(
                    QueryCode.INVALID_PARAMETERS, "Parâmetro numérico deve ser finito."
                )
            if isinstance(value, Decimal) and (not value.is_finite() or len(str(value)) > 100):
                raise RejectedSQL(QueryCode.INVALID_PARAMETERS, "Parâmetro decimal inválido.")
            if type(value) is int and not -(2**63) <= value < 2**63:
                raise RejectedSQL(
                    QueryCode.INVALID_PARAMETERS, "Inteiro fora do intervalo permitido."
                )
        return names, supplied
