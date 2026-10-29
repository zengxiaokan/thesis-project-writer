"""Synthetic evaluation fixture, release 2.0; methods expose the stored fields."""


class Repository:
    def __init__(self, connection):
        self.connection = connection

    def transaction(self):
        return self.connection

    def ticket(self, ticket_id):
        return self.connection.execute(
            "SELECT * FROM ticket WHERE id=?", (ticket_id,)
        ).fetchone()

    def candidates(self, region):
        return self.connection.execute(
            "SELECT id, active_load FROM worker WHERE region=? AND available=1 "
            "ORDER BY active_load ASC, id ASC", (region,)
        ).fetchall()

    def assign(self, ticket_id, worker_id, expected_version):
        return self.connection.execute(
            "UPDATE ticket SET worker_id=?, status='assigned', version=version+1 "
            "WHERE id=? AND status='open' AND version=?",
            (worker_id, ticket_id, expected_version),
        ).rowcount

    def add_load(self, worker_id):
        self.connection.execute(
            "UPDATE worker SET active_load=active_load+1 WHERE id=?", (worker_id,)
        )

    def enqueue_receipt(self, ticket_id, worker_id):
        return self.connection.execute(
            "INSERT INTO receipt(ticket_id, worker_id, status, attempts) "
            "VALUES (?, ?, 'pending', 0)", (ticket_id, worker_id),
        ).lastrowid

    def receipt(self, receipt_id):
        return self.connection.execute(
            "SELECT * FROM receipt WHERE id=?", (receipt_id,)
        ).fetchone()

    def pending_receipts(self, limit, max_attempts):
        return self.connection.execute(
            "SELECT id FROM receipt WHERE status='pending' AND attempts < ? "
            "ORDER BY id ASC LIMIT ?", (max_attempts, limit),
        ).fetchall()

    def record_delivery(self, receipt_id, success):
        with self.transaction():
            self.connection.execute(
                "UPDATE receipt SET attempts=attempts+1, status=? WHERE id=?",
                ("sent" if success else "pending", receipt_id),
            )
