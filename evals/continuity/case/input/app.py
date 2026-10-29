"""Synthetic static fixture; not an HTTP server."""
from registry import ROUTES, REVISION
from jobs.runner import task_registry

def application(config, repository):
    return {"revision": REVISION, "routes": ROUTES,
            "tasks": task_registry(config), "repository": repository}
