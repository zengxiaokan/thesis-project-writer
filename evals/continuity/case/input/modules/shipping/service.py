"""Synthetic dispatch consumes reservation; no external carrier API."""
from modules.inventory.service import consume
from modules.outbox.service import enqueue

def dispatch(repo, order_id):
    with repo.transaction():
        order = repo.get("orders", order_id)
        packages = repo.find("packages", lambda row: row["order_id"] == order_id and row["status"] == "packed")
        if order is None or order["status"] != "packing" or not packages:
            raise ValueError("dispatch not allowed")
        for line in order["lines"]:
            consume(repo, line["product_id"], line["quantity"])
        order["status"] = "shipped"
        shipment = repo.insert("shipments", {"order_id": order_id, "zone": order["zone"], "status": "in_transit"})
        enqueue(repo, "order_shipped", order_id)
    return shipment
