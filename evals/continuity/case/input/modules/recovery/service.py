"""Synthetic maintenance handler; configuration binds this entry."""
from modules.orders.service import cancel
from modules.outbox.service import deliver_pending

def run(repo, config, now, transport=None):
    cutoff = now - config["reservation_minutes"] * 60
    expired = repo.find("orders", lambda row: row["status"] == "reserved" and row["created_at"] < cutoff)
    cancelled = []
    for order in sorted(expired, key=lambda row: row["id"]):
        cancel(repo, order["id"], now)
        cancelled.append(order["id"])
    attempted = deliver_pending(repo, config["outbox_batch"], config["max_delivery_attempts"], transport)
    return {"cancelled": cancelled, "notification_attempts": attempted}
