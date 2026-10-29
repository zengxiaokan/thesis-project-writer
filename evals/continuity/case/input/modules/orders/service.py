"""Synthetic order orchestration, not an executed business system."""
from modules.residents.service import require_active
from modules.carts.service import lines_for
from modules.catalog.service import require_saleable
from modules.pricing.service import subtotal
from modules.coupons.service import discount
from modules.inventory import service as inventory
from modules.invoices import service as invoices
from modules.loyalty import service as loyalty
from modules.refunds import service as refunds
from modules.outbox import service as outbox

def place(repo, resident_id, now, coupon_id=None):
    resident = require_active(repo, resident_id)
    cart = lines_for(repo, resident_id)
    if not cart:
        raise ValueError("empty cart")
    lines = []
    merchants = set()
    for item in cart:
        product = require_saleable(repo, item["product_id"])
        merchants.add(product["merchant_id"])
        lines.append({"product_id": product["id"], "quantity": item["quantity"], "unit_cents": product["price_cents"]})
    if len(merchants) != 1:
        raise ValueError("one merchant per order")
    amount = subtotal(lines)
    amount -= discount(repo, coupon_id, resident_id, amount, now)
    with repo.transaction():
        for line in lines:
            inventory.reserve(repo, line["product_id"], line["quantity"])
        order = repo.insert("orders", {"resident_id": resident_id, "merchant_id": next(iter(merchants)), "zone": resident["zone"], "status": "reserved", "payment_state": "unpaid", "total_cents": amount, "created_at": now, "lines": lines})
        invoices.create(repo, order["id"], amount)
        loyalty.prepare(repo, order["id"], resident_id, amount)
        outbox.enqueue(repo, "order_created", order["id"])
    return order["id"]

def cancel(repo, order_id, now):
    with repo.transaction():
        order = repo.get("orders", order_id)
        if order is None:
            raise ValueError("order missing")
        if order["status"] != "reserved":
            raise ValueError("order cannot be cancelled")
        for line in order["lines"]:
            inventory.release(repo, line["product_id"], line["quantity"])
        order["status"] = "cancelled"
        order["cancelled_at"] = now
        if order["payment_state"] == "captured":
            refunds.issue(repo, order_id, order["total_cents"])
        invoices.void(repo, order_id)
        outbox.enqueue(repo, "order_cancelled", order_id)
    return "cancelled"
