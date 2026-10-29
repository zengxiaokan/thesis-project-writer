"""Synthetic merchant accounting; booked does not mean bank transfer."""
def accrue(repo, order_id):
    order = repo.get("orders", order_id)
    if order["status"] != "delivered":
        raise ValueError("settlement requires delivery")
    return repo.insert("settlements", {"order_id": order_id, "merchant_id": order["merchant_id"], "amount_cents": order["total_cents"], "status": "pending"})

def close(repo, merchant_id):
    rows = repo.find("settlements", lambda row: row["merchant_id"] == merchant_id and row["status"] == "pending")
    total = sum(row["amount_cents"] for row in rows)
    for row in rows:
        row["status"] = "booked"
    return {"merchant_id": merchant_id, "amount_cents": total}
