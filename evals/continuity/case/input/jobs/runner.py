"""Synthetic configuration-driven entry dispatch, with no scheduler."""
import importlib

def task_registry(config):
    return dict(config.get("job_handlers", {}))

def invoke(name, repo, config, now, transport=None):
    module_name, function_name = task_registry(config)[name].split(":", 1)
    handler = getattr(importlib.import_module(module_name), function_name)
    return handler(repo, config, now, transport)
