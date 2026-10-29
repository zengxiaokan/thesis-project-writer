"""Synthetic entry mapping; no network/authentication layer."""
from modules.residents import service as residents
from modules.catalog import service as catalog
from modules.carts import service as carts
from modules.orders import service as orders
from modules.payments import service as payments
from modules.picking import service as picking
from modules.packing import service as packing
from modules.shipping import service as shipping
from modules.delivery import service as delivery
from modules.returns import service as returns
from modules.refunds import service as refunds
from modules.settlements import service as settlements

REVISION = "synthetic-shop-1.0"
ROUTES = {
    "POST /residents": residents.register,
    "GET /catalog": catalog.list_saleable,
    "POST /cart-lines": carts.put,
    "POST /orders": orders.place,
    "POST /orders/cancel": orders.cancel,
    "POST /payments/capture": payments.capture,
    "POST /picking": picking.complete,
    "POST /packing": packing.complete,
    "POST /shipping": shipping.dispatch,
    "POST /delivery/confirm": delivery.confirm,
    "POST /returns": returns.request,
    "POST /returns/approve": returns.approve,
    "POST /refunds": refunds.issue,
    "POST /settlements/close": settlements.close,
}
