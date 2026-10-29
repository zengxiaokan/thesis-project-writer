"""Synthetic formatter; a caller-supplied transport is required."""
TEMPLATES = {"order_created": "订单已创建", "order_cancelled": "订单已取消", "order_shipped": "订单已出库"}

def send(event, transport):
    if transport is None:
        raise OSError("transport unavailable")
    transport.send({"order_id": event["order_id"], "message": TEMPLATES[event["kind"]]})
