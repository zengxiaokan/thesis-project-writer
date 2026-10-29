"""Synthetic confirmation checks the stored delivery zone."""
from modules.loyalty.service import grant
from modules.settlements.service import accrue

def confirm(repo, shipment_id, zone):
    with repo.transaction():
        shipment = repo.get("shipments", shipment_id)
        if shipment is None or shipment["status"] != "in_transit" or shipment["zone"] != zone:
            raise ValueError("delivery confirmation rejected")
        order = repo.get("orders", shipment["order_id"])
        if order["status"] != "shipped":
            raise ValueError("order not shipped")
        shipment["status"] = "delivered"
        order["status"] = "delivered"
        grant(repo, order["id"])
        accrue(repo, order["id"])
    return "delivered"
