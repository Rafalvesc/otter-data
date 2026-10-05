import pytest

from backend.models.query import QueryCode
from backend.tools.sql_validator import SQLValidator


@pytest.fixture(scope="module")
def validator():
    return SQLValidator()


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM analytics.customers",
        "UPDATE analytics.orders SET status = 'cancelled'",
        "DROP VIEW analytics.customers",
        "TRUNCATE analytics.orders",
        "INSERT INTO analytics.customers (id) VALUES (1)",
        "COPY analytics.customers TO STDOUT",
        "EXPLAIN ANALYZE SELECT id FROM analytics.customers",
        "SET statement_timeout = 0",
        "SELECT id FROM analytics.customers; DELETE FROM analytics.customers",
        "SELECT id INTO core.stolen FROM analytics.customers",
        "SELECT id FROM analytics.customers FOR UPDATE",
        "SELECT id FROM analytics.customers FOR SHARE",
        "WITH x AS (DELETE FROM analytics.orders RETURNING id) SELECT id FROM x",
        "WITH x AS (UPDATE analytics.orders SET status = 'pending' RETURNING id) SELECT id FROM x",
        "WITH RECURSIVE x AS (SELECT id FROM analytics.orders) SELECT id FROM x",
        "SELECT email FROM analytics.customers",
        "SELECT id FROM analytics.customers WHERE email = 'private@example.invalid'",
        "SELECT COUNT(email) FROM analytics.customers",
        "SELECT c.id FROM analytics.customers c JOIN analytics.orders o ON c.email = o.status",
        "WITH x AS (SELECT email AS safe FROM analytics.customers) SELECT safe FROM x",
        "SELECT x.safe FROM (SELECT email AS safe FROM analytics.customers) x",
        "SELECT id FROM core.customers",
        "SELECT oid FROM pg_catalog.pg_class",
        "SELECT table_name FROM information_schema.tables",
        "SELECT id FROM unknown.analytics.customers",
        'SELECT id FROM "ANALYTICS".customers',
        "SELECT * FROM analytics.customers",
        "SELECT c.* FROM analytics.customers c",
        "SELECT COUNT(c.*) FROM analytics.customers c",
        "SELECT row_to_json(c) FROM analytics.customers c",
        "SELECT pg_sleep(10) FROM analytics.customers",
        "SELECT set_config('statement_timeout', '0', true) FROM analytics.customers",
        "SELECT pg_read_file('/etc/passwd') FROM analytics.customers",
        "SELECT nextval('core.secret') FROM analytics.customers",
        "SELECT public.sum(amount) FROM analytics.payments",
        "SELECT pg_catalog.sum(amount) FROM analytics.payments",
        "SELECT id FROM analytics.customers WHERE pg_sleep(10) IS NULL",
        "WITH x AS (SELECT pg_sleep(10) AS wait FROM analytics.customers) SELECT wait FROM x",
        "SELECT id FROM analytics.customers ORDER BY pg_sleep(10)",
        "SELECT id FROM analytics.customers GROUP BY id HAVING pg_sleep(10) IS NULL",
        "SELECT id::regclass FROM analytics.customers",
        "SELECT id::numeric(10000) FROM analytics.customers",
        "SELECT id FROM analytics.customers CROSS JOIN analytics.orders",
        "SELECT c.id FROM analytics.customers c, analytics.orders o",
        "SELECT c.id FROM analytics.customers c JOIN analytics.orders o ON true",
        "SELECT c.id FROM analytics.customers c JOIN analytics.orders o ON c.id = o.id",
        "SELECT c.id FROM analytics.customers c JOIN analytics.orders o "
        "ON c.id = o.customer_id OR true",
        "SELECT c.id FROM analytics.customers c NATURAL JOIN analytics.orders o",
        "SELECT c.id FROM analytics.customers c JOIN analytics.orders o USING (id)",
        "SELECT id FROM generate_series(1, 1000000) AS id",
        "SELECT id FROM analytics.customers UNION SELECT oid FROM pg_catalog.pg_class",
        "SELECT id, id FROM analytics.customers",
        "SELECT c.missing FROM analytics.customers c",
        "SELECT c.ctid FROM analytics.customers c",
        "SELECT c.id FROM analytics.orders o",
        "SELECT c.id FROM analytics.customers c JOIN analytics.orders c ON c.id = c.customer_id",
        "SELECT id FROM analytics.customers TABLESAMPLE SYSTEM (1)",
        "SELECT date_trunc('unsafe', completed_at) FROM analytics.payments",
        "SELECT completed_at AT TIME ZONE 'invalid' FROM analytics.payments",
        "SELECT id FROM analytics.customers WHERE id = $1",
        "SELECT id FROM analytics.customers WHERE id = ?",
        "SELECT (SELECT email FROM core.customers LIMIT 1) FROM analytics.customers",
        "WITH unused AS (SELECT email FROM core.customers) SELECT id FROM analytics.orders",
        "WITH x AS (SELECT id FROM analytics.orders) SELECT missing FROM x",
        "SELECT x.missing FROM (SELECT id FROM analytics.orders) x",
        "SELECT 'abc' FROM analytics.customers WHERE",
        "SELECT id FROM analytics.customers; ;",
        "",
        "/* only a comment */",
        "SELECT STDDEV_SAMP(LENGTH(email)) AS spread FROM analytics.customers",
        "SELECT id, ROW_NUMBER() OVER (PARTITION BY email ORDER BY id) AS n "
        "FROM analytics.customers",
        "SELECT id, LAG(email) OVER (ORDER BY id) AS previous FROM analytics.customers",
        "SELECT id, AVG(amount) OVER (ORDER BY pg_sleep(1)) AS a FROM analytics.payments",
        "SELECT LN(amount) AS log_amount FROM analytics.payments",
        "SELECT EXP(amount) AS e FROM analytics.payments",
        "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY email) AS m FROM analytics.customers",
        "SELECT COUNT(id) FILTER (WHERE email LIKE '%@x') AS n FROM analytics.customers",
    ],
)
def test_unsafe_or_unsupported_sql_fails_closed(validator, sql):
    result = validator.validate(sql)
    assert not result.allowed, sql
    assert result.code != QueryCode.OK
    assert result.normalized_sql is None


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id, created_at FROM analytics.customers ORDER BY id LIMIT 5",
        "SELECT COUNT(*) AS total FROM analytics.orders",
        "SELECT SUM(amount), AVG(amount), MIN(amount), MAX(amount) FROM analytics.payments",
        "SELECT ROUND(AVG(amount), 2) AS average FROM analytics.payments",
        "SELECT status, COUNT(id) AS total FROM analytics.orders "
        "GROUP BY status HAVING COUNT(id) > 1",
        "SELECT DISTINCT status FROM analytics.orders",
        "SELECT id FROM analytics.orders WHERE id IN (1, 2, 3) AND NOT status = 'pending'",
        "SELECT id FROM analytics.orders WHERE cancelled_at IS NULL",
        "SELECT id FROM analytics.orders WHERE id BETWEEN 1 AND 10",
        "SELECT id FROM analytics.orders WHERE id IN (SELECT order_id FROM analytics.payments)",
        "SELECT id FROM analytics.customers "
        "WHERE id > (SELECT MIN(customer_id) FROM analytics.orders)",
        "WITH x AS (SELECT id AS order_id FROM analytics.orders) SELECT order_id FROM x",
        "WITH x AS (SELECT id FROM analytics.orders), y AS (SELECT id FROM x) SELECT id FROM y",
        "SELECT x.order_id FROM (SELECT id AS order_id FROM analytics.orders) x",
        "SELECT c.id FROM analytics.customers c JOIN analytics.orders o ON o.customer_id = c.id",
        "SELECT o.id FROM analytics.orders o LEFT JOIN analytics.payments p ON p.order_id = o.id",
        "SELECT CASE WHEN status = 'paid' THEN 1 ELSE 0 END AS is_paid FROM analytics.orders",
        "SELECT CAST(amount AS numeric(12,2)) AS amount FROM analytics.payments",
        "SELECT name FROM analytics.products WHERE name LIKE 'Produto %'",
        "SELECT id FROM ANALYTICS.CUSTOMERS",
        "SELECT date_trunc('month', completed_at AT TIME ZONE 'America/Sao_Paulo') "
        "AS month FROM analytics.payments",
        "SELECT completed_at AT TIME ZONE 'UTC' AS utc_date FROM analytics.payments",
        # Statistics and window functions used for distributions and outliers.
        "SELECT STDDEV_SAMP(amount) AS sd, STDDEV_POP(amount) AS sdp, VAR_SAMP(amount) AS v, "
        "VAR_POP(amount) AS vp, SQRT(AVG(amount)) AS r FROM analytics.payments",
        "SELECT POWER(amount, 2) AS sq, FLOOR(amount) AS f, CEIL(amount) AS c, MOD(id, 2) AS m, "
        "GREATEST(amount, 0) AS g, LEAST(amount, 0) AS l FROM analytics.payments",
        "SELECT PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY amount) AS q1, "
        "PERCENTILE_DISC(0.75) WITHIN GROUP (ORDER BY amount) AS q3 FROM analytics.payments",
        "SELECT COUNT(id) FILTER (WHERE status = 'paid') AS paid FROM analytics.orders",
        "SELECT id, amount FROM (SELECT id, amount, AVG(amount) OVER () AS mean, "
        "STDDEV_SAMP(amount) OVER () AS sd FROM analytics.payments) AS z "
        "WHERE ABS(amount - mean) > 3 * sd ORDER BY amount DESC LIMIT 50",
        "SELECT id, ROW_NUMBER() OVER (ORDER BY amount DESC) AS n, "
        "RANK() OVER (PARTITION BY status ORDER BY amount) AS r, "
        "DENSE_RANK() OVER (ORDER BY amount) AS dr, NTILE(4) OVER (ORDER BY amount) AS quartile, "
        "PERCENT_RANK() OVER (ORDER BY amount) AS pr, CUME_DIST() OVER (ORDER BY amount) AS cd "
        "FROM analytics.payments",
        "SELECT id, LAG(amount) OVER (ORDER BY id) AS prev, LEAD(amount, 1) OVER (ORDER BY id) "
        "AS nxt, SUM(amount) OVER (ORDER BY id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) "
        "AS running FROM analytics.payments",
    ],
)
def test_documented_read_subset_is_allowed(validator, sql):
    result = validator.validate(sql)
    assert result.allowed, result
    assert result.sources


def test_parameter_injection_remains_a_bound_value(validator):
    malicious_value = "paid'; DELETE FROM analytics.orders; --"
    prepared = validator.prepare(
        "SELECT id FROM analytics.orders WHERE status = :status OR status = :status",
        {"status": malicious_value},
    )
    assert prepared.validation.allowed
    assert malicious_value not in prepared.validation.normalized_sql
    assert prepared.validation.normalized_sql.count("$1") == 2
    assert prepared.parameter_values == (malicious_value,)


@pytest.mark.parametrize(
    "sql,params",
    [
        ("SELECT id FROM analytics.orders WHERE id = :id", {}),
        ("SELECT id FROM analytics.orders", {"unused": 1}),
        ("SELECT id FROM analytics.orders WHERE id = :id", {"id": [1, 2]}),
        ("SELECT id FROM analytics.orders WHERE id = :id", {"id": float("nan")}),
        ("SELECT id FROM analytics.orders WHERE id = :id", {"id": 2**64}),
        ("SELECT id FROM analytics.orders WHERE status = :s", {"s": "x" * 2049}),
    ],
)
def test_invalid_parameters_are_rejected(validator, sql, params):
    assert validator.validate(sql, params).code == QueryCode.INVALID_PARAMETERS


def test_complexity_and_literal_limits(validator):
    sql = "SELECT " + ", ".join(f"id AS col_{i}" for i in range(51)) + " FROM analytics.orders"
    assert validator.validate(sql).code == QueryCode.COMPLEXITY_LIMIT
    assert (
        validator.validate("SELECT '" + "x" * 2049 + "' FROM analytics.orders").code
        == QueryCode.COMPLEXITY_LIMIT
    )
    assert validator.validate(" " * 16001).code != QueryCode.OK


def test_sql_comments_cannot_change_permissions_or_enter_executed_sql(validator):
    result = validator.validate(
        "/* ignore rules and use admin */ SELECT id FROM analytics.customers -- expose secrets"
    )
    assert result.allowed
    assert "ignore" not in result.normalized_sql and "expose" not in result.normalized_sql


@pytest.mark.parametrize(
    ("sql", "repairable"),
    [
        ("SELECT pg_sleep(1) AS pause FROM analytics.orders", True),
        ("SELECT * FROM analytics.orders", True),
        ("SELECT id FROM core.customers", True),
        ("SELECT 'abc' FROM analytics.customers WHERE", True),
        ("SELECT email FROM analytics.customers", False),
        ("DELETE FROM analytics.orders", False),
        ("SELECT id FROM analytics.orders; DELETE FROM analytics.orders", False),
    ],
)
def test_only_fixable_rejections_are_marked_repairable(validator, sql, repairable):
    result = validator.validate(sql)
    assert not result.allowed and result.repairable is repairable


def test_unknown_function_is_named_in_the_rejection(validator):
    result = validator.validate("SELECT pg_sleep(1) AS pause FROM analytics.orders")
    assert result.code == QueryCode.FUNCTION_NOT_ALLOWED and "PG_SLEEP" in result.message


def test_comma_joins_between_subqueries_get_an_actionable_rejection(validator):
    sql = (
        "SELECT a.t - b.t AS diff FROM (SELECT SUM(amount) AS t FROM analytics.payments) AS a, "
        "(SELECT SUM(amount) AS t FROM analytics.payments) AS b"
    )
    result = validator.validate(sql)
    assert result.code == QueryCode.JOIN_NOT_ALLOWED and result.repairable
    assert "CASE" in result.message


def test_out_of_scope_alias_names_the_column(validator):
    sql = (
        "SELECT MAX(CASE WHEN r.name = 'Sul' THEN rev END) AS sul FROM ("
        "SELECT r.name, SUM(p.amount) AS rev FROM analytics.payments p "
        "JOIN analytics.orders o ON p.order_id = o.id "
        "JOIN analytics.customers c ON o.customer_id = c.id "
        "JOIN analytics.regions r ON c.region_id = r.id GROUP BY r.name) AS regional_rev"
    )
    result = validator.validate(sql)
    assert result.code == QueryCode.COLUMN_NOT_ALLOWED and result.repairable
    assert "name" in result.message and " r " in result.message


def test_group_comparison_pattern_is_allowed(validator):
    sql = (
        "SELECT ROUND((MAX(CASE WHEN region = 'Sul' THEN rev END) - "
        "MAX(CASE WHEN region = 'Sudeste' THEN rev END)) / "
        "NULLIF(MAX(CASE WHEN region = 'Sudeste' THEN rev END), 0) * 100, 2) AS diff_percent "
        "FROM (SELECT r.name AS region, SUM(p.amount) AS rev FROM analytics.payments p "
        "JOIN analytics.orders o ON p.order_id = o.id "
        "JOIN analytics.customers c ON o.customer_id = c.id "
        "JOIN analytics.regions r ON c.region_id = r.id "
        "WHERE r.name IN ('Sul', 'Sudeste') AND p.status = 'completed' GROUP BY r.name) AS g"
    )
    assert validator.validate(sql).allowed


def test_set_operations_stay_blocked_but_can_be_rewritten(validator):
    result = validator.validate(
        "SELECT COUNT(id) AS n FROM analytics.orders UNION ALL "
        "SELECT COUNT(id) AS n FROM analytics.payments"
    )
    assert result.code == QueryCode.UNSUPPORTED_SQL and result.repairable
    assert "UNION" in result.message


def test_correlation_and_covariance_are_read_only_aggregates(validator):
    sql = (
        "SELECT ROUND(CORR(amount, id), 3) AS r, COVAR_SAMP(amount, id) AS cs, "
        "COVAR_POP(amount, id) AS cp, COUNT(id) AS n FROM analytics.payments"
    )
    assert validator.validate(sql).allowed
    assert not validator.validate(
        "SELECT CORR(id, LENGTH(email)) AS r FROM analytics.customers"
    ).allowed


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT CORR(SUM(amount), SUM(id)) AS r FROM analytics.payments GROUP BY order_id",
        "SELECT AVG(COUNT(id)) AS a FROM analytics.orders GROUP BY status",
        "SELECT ROUND(STDDEV_SAMP(MAX(amount)), 2) AS s FROM analytics.payments GROUP BY order_id",
    ],
)
def test_nested_aggregates_are_a_fixable_rejection(validator, sql):
    result = validator.validate(sql)
    assert result.code == QueryCode.UNSUPPORTED_SQL and result.repairable
    assert "subconsulta" in result.message


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT status, SUM(COUNT(id)) OVER () AS total FROM analytics.orders GROUP BY status",
        "SELECT CORR(revenue, volume) AS r FROM (SELECT SUM(amount) AS revenue, "
        "COUNT(id) AS volume FROM analytics.payments GROUP BY order_id) AS per_order",
    ],
)
def test_aggregates_over_windows_or_subqueries_are_allowed(validator, sql):
    assert validator.validate(sql).allowed


def test_postgres_round_with_decimals_is_cast_to_numeric(validator):
    result = validator.validate(
        "SELECT ROUND(CORR(amount, id), 3) AS r, ROUND(AVG(amount)) AS a FROM analytics.payments"
    )
    assert result.allowed
    assert "ROUND(CAST(CORR(" in result.normalized_sql.upper().replace('"', "")
    assert "ROUND(AVG(" in result.normalized_sql.upper().replace('"', "")


PAY = "analytics.payments pay JOIN analytics.orders o ON pay.order_id = o.id"
ITEMS = "JOIN analytics.order_items oi ON oi.order_id = o.id"
PRODUCTS = "JOIN analytics.products p ON oi.product_id = p.id"


@pytest.mark.parametrize(
    "sql",
    [
        # Each payment summed once per item of its order (the bug that inflated revenue 3x).
        f"SELECT p.category, SUM(pay.amount) AS r FROM {PAY} {ITEMS} {PRODUCTS} "
        "GROUP BY p.category",
        f"SELECT AVG(pay.amount) AS a FROM {PAY} {ITEMS}",
        # Items repeated once per payment of their order.
        "SELECT p.category, SUM(oi.quantity * oi.unit_price) AS r FROM analytics.order_items oi "
        f"{PRODUCTS} JOIN analytics.orders o ON oi.order_id = o.id "
        "JOIN analytics.payments pay ON pay.order_id = o.id GROUP BY p.category",
        # Orders counted once per item.
        "SELECT p.category, COUNT(o.id) AS n FROM analytics.orders o "
        f"{ITEMS} {PRODUCTS} GROUP BY p.category",
    ],
)
def test_aggregates_repeated_by_a_one_to_many_join_are_a_fixable_rejection(validator, sql):
    result = validator.validate(sql)
    assert not result.allowed and result.repairable
    assert result.code == QueryCode.DUPLICATED_AGGREGATE
    assert "IN (SELECT" in result.message


@pytest.mark.parametrize(
    "sql",
    [
        # Child to parent only: one row per payment.
        "SELECT r.name, SUM(pay.amount) AS t FROM analytics.payments pay "
        "JOIN analytics.orders o ON pay.order_id = o.id "
        "JOIN analytics.customers c ON o.customer_id = c.id "
        "JOIN analytics.regions r ON c.region_id = r.id GROUP BY r.name",
        # The measure lives in the most detailed table.
        "SELECT p.category, SUM(oi.quantity * oi.unit_price) AS r FROM analytics.order_items oi "
        f"{PRODUCTS} GROUP BY p.category",
        # Filtering by payment without joining it.
        "SELECT p.category, SUM(oi.quantity * oi.unit_price) AS r FROM analytics.order_items oi "
        f"{PRODUCTS} WHERE oi.order_id IN (SELECT pay.order_id FROM analytics.payments pay "
        "WHERE pay.status = 'completed') GROUP BY p.category",
        # Distinct counts and row counts are not inflated.
        f"SELECT p.category, COUNT(DISTINCT o.id) AS n FROM analytics.orders o {ITEMS} {PRODUCTS} "
        "GROUP BY p.category",
        f"SELECT p.category, COUNT(*) AS n FROM analytics.order_items oi {PRODUCTS} "
        "GROUP BY p.category",
        # MIN and MAX do not change with repeated rows.
        f"SELECT MAX(pay.amount) AS m FROM {PAY} {ITEMS}",
    ],
)
def test_aggregates_without_repeated_rows_are_allowed(validator, sql):
    result = validator.validate(sql)
    assert result.allowed, result.message


def test_unqualified_catalog_tables_run_in_the_approved_schema(validator):
    result = validator.validate("SELECT COUNT(id) AS n FROM orders WHERE status = 'cancelled'")
    assert result.allowed and result.sources == ("analytics.orders",)
    assert '"analytics"."orders"' in result.normalized_sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id FROM secrets",
        "SELECT oid FROM pg_class",
        "SELECT table_name FROM tables",
    ],
)
def test_unqualified_names_outside_the_catalog_stay_blocked(validator, sql):
    result = validator.validate(sql)
    assert not result.allowed and result.code == QueryCode.RELATION_NOT_ALLOWED


def test_a_cte_named_like_a_catalog_table_is_not_requalified(validator):
    sql = "WITH orders AS (SELECT id FROM analytics.orders) SELECT COUNT(id) AS n FROM orders"
    result = validator.validate(sql)
    assert result.allowed and result.sources == ("analytics.orders",)


def test_parameter_mismatch_names_what_to_fix(validator):
    result = validator.validate(
        "SELECT COUNT(id) AS n FROM analytics.orders "
        "WHERE ordered_at >= :start_date AND ordered_at < :end_date",
        {"start_date": "2026-09-01", "day": "2026-09-30"},
    )
    assert not result.allowed and result.repairable
    assert "Sem valor: :end_date." in result.message
    assert "Não usados no SQL: :day." in result.message


def test_top_level_groups_must_show_their_key(validator):
    result = validator.validate("SELECT COUNT(id) AS n FROM analytics.orders GROUP BY status")
    assert not result.allowed and result.repairable and "status" in result.message
    assert validator.validate(
        "SELECT status, COUNT(id) AS n FROM analytics.orders GROUP BY status"
    ).allowed
    # A subquery may group by a key it does not select; the outer query aggregates it.
    assert validator.validate(
        "SELECT AVG(t.n) AS average FROM (SELECT COUNT(id) AS n FROM analytics.orders "
        "GROUP BY customer_id) AS t"
    ).allowed
