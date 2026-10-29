"""Synthetic evaluation fixture: transfer-core 2.2 SQLite storage behavior."""
from contextlib import contextmanager
import sqlite3


class Repository:
    def __init__(self, path):
        self.connection = sqlite3.connect(path, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")

    @contextmanager
    def transaction(self):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def take_stock(self, warehouse_id, sku, pieces):
        return self.connection.execute(
            "UPDATE stock SET pieces=pieces-? "
            "WHERE warehouse_id=? AND sku=? AND pieces>=?",
            (pieces, warehouse_id, sku, pieces),
        ).rowcount

    def insert_transfer(self, request_key, source, destination, sku, pieces):
        return self.connection.execute(
            "INSERT INTO transfers(request_key,source_warehouse,destination_warehouse,"
            "sku,pieces,status) VALUES(?,?,?,?,?,'in_transit')",
            (request_key, source, destination, sku, pieces),
        ).lastrowid

    def get_transfer(self, transfer_id):
        return self.connection.execute(
            "SELECT * FROM transfers WHERE id=?", (transfer_id,)
        ).fetchone()

    def mark_received(self, transfer_id):
        return self.connection.execute(
            "UPDATE transfers SET status='received' "
            "WHERE id=? AND status='in_transit'", (transfer_id,),
        ).rowcount

    def add_stock(self, warehouse_id, sku, pieces):
        self.connection.execute(
            "INSERT INTO stock(warehouse_id,sku,pieces) VALUES(?,?,?) "
            "ON CONFLICT(warehouse_id,sku) DO UPDATE SET pieces=pieces+excluded.pieces",
            (warehouse_id, sku, pieces),
        )
