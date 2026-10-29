"""Synthetic delivery-triggered points posting, amount measured in cents."""
def prepare(repo, order_id, resident_id, amount_cents):
    return repo.insert("loyalty", {"order_id": order_id, "resident_id": resident_id, "points": amount_cents // 100, "status": "pending"})

def grant(repo, order_id):
    order = repo.get("orders", order_id)
    rows = repo.find("loyalty", lambda row: row["order_id"] == order_id and row["status"] == "pending")
    if order["status"] != "delivered" or not rows:
        raise ValueError("points posting rejected")
    row = rows[0]
    resident = repo.get("residents", row["resident_id"])
    resident["points"] += row["points"]
    row["status"] = "posted"
