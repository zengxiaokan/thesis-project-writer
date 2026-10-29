"""Synthetic requested/approved return records; no automatic refund/restock."""
def request(repo, order_id, reason):
    order = repo.get("orders", order_id)
    if order is None or order["status"] != "delivered" or not reason.strip():
        raise ValueError("return request rejected")
    return repo.insert("returns", {"order_id": order_id, "reason": reason, "status": "requested"})

def approve(repo, return_id):
    row = repo.get("returns", return_id)
    if row is None or row["status"] != "requested":
        raise ValueError("approval rejected")
    row["status"] = "approved"
    return row
