"""Synthetic evaluation fixture, release 2.0."""
from notifications import deliver_receipt


class NotFound(Exception):
    pass


class DispatchConflict(Exception):
    pass


class NoCandidate(Exception):
    pass


def dispatch_ticket(repo, transport, ticket_id, expected_version):
    with repo.transaction():
        ticket = repo.ticket(ticket_id)
        if ticket is None:
            raise NotFound()
        if ticket["status"] != "open":
            raise DispatchConflict()
        candidates = repo.candidates(ticket["region"])
        if not candidates:
            raise NoCandidate()
        worker_id = candidates[0]["id"]
        if repo.assign(ticket_id, worker_id, expected_version) != 1:
            raise DispatchConflict()
        repo.add_load(worker_id)
        receipt_id = repo.enqueue_receipt(ticket_id, worker_id)

    # Assignment, load increment, and receipt creation have committed here.
    notification = deliver_receipt(repo, transport, receipt_id)
    return {"ticket_id": ticket_id, "worker_id": worker_id,
            "status": "assigned", "notification": notification}
