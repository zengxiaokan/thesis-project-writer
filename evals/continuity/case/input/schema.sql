-- Synthetic design draft ONLY. store.py does not execute this SQL.
CREATE TABLE resident (id INTEGER PRIMARY KEY, name TEXT, zone TEXT, active INTEGER);
CREATE TABLE product (id INTEGER PRIMARY KEY, merchant_id INTEGER, price_cents INTEGER, saleable INTEGER);
CREATE TABLE customer_order (id INTEGER PRIMARY KEY, resident_id INTEGER REFERENCES resident(id), merchant_id INTEGER, status TEXT, payment_state TEXT, total_cents INTEGER, created_at INTEGER);
CREATE TABLE order_line (order_id INTEGER, product_id INTEGER, quantity INTEGER, unit_cents INTEGER);
CREATE TABLE inventory (product_id INTEGER, available INTEGER, reserved INTEGER);
CREATE TABLE payment (id INTEGER PRIMARY KEY, order_id INTEGER, amount_cents INTEGER, refunded_cents INTEGER);
CREATE TABLE invoice (id INTEGER PRIMARY KEY, order_id INTEGER UNIQUE, status TEXT, amount_cents INTEGER);
CREATE TABLE outbox_event (id INTEGER PRIMARY KEY, kind TEXT, order_id INTEGER, status TEXT, attempts INTEGER);
CREATE TABLE pick_record (id INTEGER PRIMARY KEY, order_id INTEGER, status TEXT);
CREATE TABLE package_record (id INTEGER PRIMARY KEY, order_id INTEGER, status TEXT);
CREATE TABLE shipment (id INTEGER PRIMARY KEY, order_id INTEGER, zone TEXT, status TEXT);
CREATE TABLE return_request (id INTEGER PRIMARY KEY, order_id INTEGER, reason TEXT, status TEXT);
CREATE TABLE refund (id INTEGER PRIMARY KEY, order_id INTEGER, amount_cents INTEGER);
CREATE TABLE loyalty (id INTEGER PRIMARY KEY, order_id INTEGER UNIQUE, resident_id INTEGER, points INTEGER, status TEXT);
CREATE TABLE settlement (id INTEGER PRIMARY KEY, order_id INTEGER, merchant_id INTEGER, amount_cents INTEGER, status TEXT);
