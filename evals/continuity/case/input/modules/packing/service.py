"""Synthetic package creation leaves the order in packing status."""
def complete(repo, order_id):
    order = repo.get("orders", order_id)
    picks = repo.find("picks", lambda row: row["order_id"] == order_id and row["status"] == "done")
    if order is None or order["status"] != "packing" or not picks:
        raise ValueError("packing not allowed")
    if repo.find("packages", lambda row: row["order_id"] == order_id):
        raise ValueError("package exists")
    return repo.insert("packages", {"order_id": order_id, "status": "packed"})
