CREATE SCHEMA core;
CREATE SCHEMA analytics;

CREATE TABLE core.regions (
    id integer PRIMARY KEY,
    name text NOT NULL,
    state char(2) NOT NULL UNIQUE
);

CREATE TABLE core.customers (
    id integer PRIMARY KEY,
    region_id integer NOT NULL REFERENCES core.regions(id),
    created_at timestamptz NOT NULL,
    email text NOT NULL UNIQUE
);

CREATE TABLE core.products (
    id integer PRIMARY KEY,
    name text NOT NULL,
    category text NOT NULL,
    current_price numeric(12,2) NOT NULL CHECK (current_price >= 0)
);

CREATE TABLE core.orders (
    id integer PRIMARY KEY,
    customer_id integer NOT NULL REFERENCES core.customers(id),
    ordered_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('paid', 'cancelled', 'pending')),
    cancelled_at timestamptz,
    CHECK ((status = 'cancelled') = (cancelled_at IS NOT NULL)),
    CHECK (cancelled_at IS NULL OR cancelled_at >= ordered_at)
);

CREATE TABLE core.order_items (
    id integer PRIMARY KEY,
    order_id integer NOT NULL REFERENCES core.orders(id),
    product_id integer NOT NULL REFERENCES core.products(id),
    quantity integer NOT NULL CHECK (quantity > 0),
    unit_price numeric(12,2) NOT NULL CHECK (unit_price >= 0),
    UNIQUE (order_id, product_id)
);

CREATE TABLE core.payments (
    id integer PRIMARY KEY,
    order_id integer NOT NULL REFERENCES core.orders(id),
    amount numeric(12,2) NOT NULL CHECK (amount >= 0),
    status text NOT NULL CHECK (status IN ('completed', 'failed', 'pending')),
    completed_at timestamptz,
    CHECK ((status = 'completed') = (completed_at IS NOT NULL))
);

CREATE INDEX ON core.customers (created_at);
CREATE INDEX ON core.customers (region_id);
CREATE INDEX ON core.orders (customer_id);
CREATE INDEX ON core.orders (ordered_at);
CREATE INDEX ON core.orders (cancelled_at) WHERE status = 'cancelled';
CREATE INDEX ON core.payments (order_id);
CREATE INDEX ON core.payments (completed_at) WHERE status = 'completed';

-- Default owner-rights views intentionally hide core.customers.email.
CREATE VIEW analytics.regions WITH (security_barrier=true) AS
    SELECT id, name, state FROM core.regions;
CREATE VIEW analytics.customers WITH (security_barrier=true) AS
    SELECT id, region_id, created_at FROM core.customers;
CREATE VIEW analytics.products WITH (security_barrier=true) AS
    SELECT id, name, category, current_price FROM core.products;
CREATE VIEW analytics.orders WITH (security_barrier=true) AS
    SELECT id, customer_id, ordered_at, status, cancelled_at FROM core.orders;
CREATE VIEW analytics.order_items WITH (security_barrier=true) AS
    SELECT id, order_id, product_id, quantity, unit_price FROM core.order_items;
CREATE VIEW analytics.payments WITH (security_barrier=true) AS
    SELECT id, order_id, amount, status, completed_at FROM core.payments;

