#!/usr/bin/env python3
"""Read-only local-file helpers for explicit thesis audit scopes (Python 3.8+)."""
import hashlib
import json
from pathlib import Path
import stat


class InputError(ValueError):
    pass


def resolved_path(path, strict=False):
    try:
        return path.resolve(strict=strict)
    except RuntimeError as error:
        raise InputError("Cannot resolve audit path (possibly a link loop): " + str(path)) from error


def is_link(path):
    try:
        entry = path.lstat()
    except FileNotFoundError:
        return False
    return (stat.S_ISLNK(entry.st_mode)
            or bool(getattr(entry, "st_file_attributes", 0) & 0x400))


class Reader:
    """No project imports, network, writes, or persistent cache."""
    def __init__(self, root):
        selected = Path(root).expanduser().absolute()
        if is_link(selected):
            raise InputError("Read root must not be a symbolic link or reparse point")
        self.root = resolved_path(selected, strict=True)
        if not self.root.is_dir():
            raise InputError("Read root must be an existing directory")
        self.accessed = set()

    def path(self, relative, base=None):
        if not isinstance(relative, str) or not relative or "\x00" in relative:
            raise InputError("Expected a non-empty relative file path")
        if Path(relative).is_absolute() or ":" in relative:
            raise InputError("File paths must be relative to the selected read root")
        # Both slash forms have the same scope meaning on every supported OS.
        relative = relative.replace("\\", "/")
        parent = self.root if base is None else self.root / base
        candidate = parent / relative
        resolved = resolved_path(candidate)
        try:
            resolved.relative_to(self.root)
        except ValueError:
            raise InputError("Path escapes the selected read root: " + relative)
        for part in [candidate, *candidate.parents]:
            if part == self.root:
                break
            if is_link(part):
                raise InputError("Linked or reparse-point audit path is not supported: " + relative)
        return resolved

    def name(self, path):
        return Path(path).relative_to(self.root).as_posix()

    def read_bytes(self, relative):
        path = self.path(relative)
        if not path.is_file():
            raise FileNotFoundError("File does not exist: " + relative)
        data = path.read_bytes()
        self.accessed.add(self.name(path))
        return data

    def read_text(self, relative):
        try:
            return self.read_bytes(relative).decode("utf-8-sig")
        except UnicodeError as error:
            raise InputError("Text must be UTF-8: " + relative) from error

    def load_json(self, relative):
        def reject_constant(value):
            raise InputError("Invalid JSON number: " + value)

        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise InputError("Duplicate JSON key: " + key)
                result[key] = value
            return result
        try:
            return json.loads(self.read_text(relative), object_pairs_hook=unique_pairs,
                              parse_constant=reject_constant)
        except json.JSONDecodeError as error:
            raise InputError("Invalid JSON at %s:%s: %s" % (relative, error.lineno, error.msg)) from error

    def fingerprint(self, relative, mode="bytes"):
        if mode not in ("bytes", "text-lf"):
            raise InputError("Unknown hash_mode: " + str(mode))
        data = self.read_bytes(relative)
        if mode == "text-lf":
            data = data.replace(b"\r\n", b"\n")
        return hashlib.sha256(data).hexdigest()


def finding(code, message, path=None, line=None, severity="warning", **details):
    value = {"code": code, "severity": severity, "message": message}
    if path is not None:
        value["path"] = path
    if line is not None:
        value["line"] = line
    if details:
        value["details"] = details
    return value


def print_report(report):
    print(json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False))
