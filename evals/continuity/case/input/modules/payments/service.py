"""Synthetic local payment ledger, no payment gateway."""
def capture(repo, order_id, amount_cents):
    with repo.transaction():
        order = repo.get("orders", order_id)
        if order is None or order["status"] != "reserved" or order["payment_state"] != "unpaid":
            raise ValueError("payment not allowed")
        if amount_cents != order["total_cents"]:
            raise ValueError("amount mismatch")
        row = repo.insert("payments", {"order_id": order_id, "amount_cents": amount_cents, "refunded_cents": 0})
        order["payment_state"] = "captured"
    return row
