"""Synthetic local refund ledger; caller controls transaction."""
def issue(repo, order_id, amount_cents):
    order = repo.get("orders", order_id)
    approved = repo.find("returns", lambda row: row["order_id"] == order_id and row["status"] == "approved")
    if order is None or (order["status"] != "cancelled" and not approved):
        raise ValueError("refund not allowed")
    payments = repo.find("payments", lambda row: row["order_id"] == order_id)
    if not payments or type(amount_cents) is not int or amount_cents <= 0:
        raise ValueError("payment or amount invalid")
    payment = payments[0]
    if amount_cents > payment["amount_cents"] - payment["refunded_cents"]:
        raise ValueError("refund exceeds captured balance")
    payment["refunded_cents"] += amount_cents
    if payment["refunded_cents"] == payment["amount_cents"]:
        order["payment_state"] = "refunded"
    return repo.insert("refunds", {"order_id": order_id, "amount_cents": amount_cents})
