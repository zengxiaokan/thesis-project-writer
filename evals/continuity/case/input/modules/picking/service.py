"""Synthetic picking moves paid reserved orders to packing."""
def complete(repo, order_id):
    with repo.transaction():
        order = repo.get("orders", order_id)
        if order is None or order["status"] != "reserved" or order["payment_state"] != "captured":
            raise ValueError("picking not allowed")
        repo.insert("picks", {"order_id": order_id, "status": "done"})
        order["status"] = "packing"
    return "packing"
