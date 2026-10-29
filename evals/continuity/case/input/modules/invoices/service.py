"""Synthetic invoice record, not a fiscal invoice integration."""
def create(repo, order_id, amount_cents):
    if repo.find("invoices", lambda row: row["order_id"] == order_id):
        raise ValueError("invoice exists")
    return repo.insert("invoices", {"order_id": order_id, "amount_cents": amount_cents, "status": "issued"})

def void(repo, order_id):
    rows = repo.find("invoices", lambda row: row["order_id"] == order_id)
    if not rows:
        raise ValueError("invoice missing")
    rows[0]["status"] = "void"
