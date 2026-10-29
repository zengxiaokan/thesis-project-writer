"""Synthetic single-process memory store; no SQL execution/durability/locks."""
from contextlib import contextmanager
from copy import deepcopy

TABLES = ("residents", "catalog", "cart_lines", "coupons", "inventory", "orders",
          "payments", "invoices", "picks", "packages", "shipments", "returns",
          "refunds", "outbox", "loyalty", "settlements")

class Store:
    def __init__(self):
        self.rows = {name: [] for name in TABLES}
        self.sequence = {name: 0 for name in TABLES}

    def get(self, table, row_id):
        return next((row for row in self.rows[table] if row["id"] == row_id), None)

    def find(self, table, predicate):
        return [row for row in self.rows[table] if predicate(row)]

    def insert(self, table, values):
        self.sequence[table] += 1
        row = dict(values, id=self.sequence[table])
        self.rows[table].append(row)
        return row

    @contextmanager
    def transaction(self):
        snapshot = deepcopy((self.rows, self.sequence))
        try:
            yield
        except Exception:
            self.rows, self.sequence = snapshot
            raise
