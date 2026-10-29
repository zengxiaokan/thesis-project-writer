"""Synthetic pending notification queue with a bounded attempt count."""
from modules.notifications.service import send

def enqueue(repo, kind, order_id):
    return repo.insert("outbox", {"kind": kind, "order_id": order_id, "status": "pending", "attempts": 0})

def deliver_pending(repo, limit, max_attempts, transport):
    eligible = repo.find("outbox", lambda row: row["status"] == "pending" and row["attempts"] < max_attempts)
    selected = sorted(eligible, key=lambda row: row["id"])[:limit]
    for event in selected:
        try:
            send(event, transport)
        except OSError:
            event["attempts"] += 1
        else:
            event["attempts"] += 1
            event["status"] = "sent"
    return len(selected)
