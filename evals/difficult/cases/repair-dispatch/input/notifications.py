"""Synthetic evaluation fixture, release 2.0; transport is supplied by a caller."""


def deliver_receipt(repo, transport, receipt_id):
    receipt = repo.receipt(receipt_id)
    if receipt["status"] == "sent":
        return "sent"
    try:
        transport.send(receipt["worker_id"], receipt["ticket_id"])
    except OSError:
        repo.record_delivery(receipt_id, success=False)
        return "pending"
    repo.record_delivery(receipt_id, success=True)
    return "sent"


def retry_pending(repo, transport, limit, max_attempts):
    results = []
    for row in repo.pending_receipts(limit, max_attempts):
        results.append((row["id"], deliver_receipt(repo, transport, row["id"])))
    return results
