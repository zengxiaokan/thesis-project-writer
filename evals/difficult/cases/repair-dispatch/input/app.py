"""Synthetic evaluation fixture, release 2.0; no production server is provided."""
import json
from pathlib import Path
import sqlite3

from dispatch import DispatchConflict, NoCandidate, NotFound, dispatch_ticket
from notifications import retry_pending
from repository import Repository


def create_app(database_path, transport):
    config = json.loads(Path(__file__).with_name("project.json").read_text(encoding="utf-8"))
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    repo = Repository(connection)

    def dispatch_endpoint(request):
        # role is supplied by the caller; this fixture has no login/token layer.
        if request["role"] not in ("dispatcher", "admin"):
            return 403, {"error": "role_forbidden"}
        try:
            result = dispatch_ticket(repo, transport, request["ticket_id"], request["version"])
        except NotFound:
            return 404, {"error": "ticket_not_found"}
        except (DispatchConflict, NoCandidate):
            return 409, {"error": "dispatch_conflict"}
        return 200, result

    routes = {"POST /tickets/dispatch": dispatch_endpoint}
    tasks = {
        "retry_dispatch_receipts": lambda: retry_pending(
            repo, transport,
            limit=config["retry_batch_size"],
            max_attempts=config["notification_max_attempts"],
        )
    }
    # Registration only: no scheduler frequency or actual invocation is supplied.
    return {"routes": routes, "tasks": tasks, "repository": repo}
