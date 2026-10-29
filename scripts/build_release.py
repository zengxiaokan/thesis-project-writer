#!/usr/bin/env python3
"""Build or check the portable distribution using only the Python standard library."""
import argparse
import io
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (".gitattributes", ".gitignore", "README.md", "SKILL.md", "LICENSE", "VERSION", "CHANGELOG.md")
SOURCE_GROUPS = {"agents": (".yaml",), "references": (".md",),
                 "scripts": (".py",), "tests": (".py",),
                 "evals": (".json",),
                 "examples": (".md", ".json", ".mmd", ".dot", ".svg", ".csv", ".py"),
                 "docs": (".md",)}


def canonical_bytes(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")


def release_files(root):
    root = Path(root)
    result = {Path(name) for name in ROOT_FILES}
    for folder, suffixes in SOURCE_GROUPS.items():
        for path in (root / folder).rglob("*"):
            if folder == "evals" and path.relative_to(root / folder) != Path("evals.json"):
                continue
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in suffixes:
                result.add(path.relative_to(root))
    for relative in result:
        path = root / relative
        path.resolve().relative_to(root.resolve())
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing or linked release source: " + str(relative))
    return sorted(result, key=lambda path: path.as_posix())


def make_archive(root=ROOT):
    root = Path(root)
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("VERSION must be a three-component version")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for relative in release_files(root):
            name = "thesis-project-writer/" + relative.as_posix()
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, canonical_bytes(root / relative))
    return stream.getvalue()


def verify_links(root=ROOT):
    # Reuse the audit parser so code examples, angle-bracket destinations and
    # balanced parentheses do not become false broken links in the release.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_consistency import visible_lines, image_targets

    root = Path(root)
    for relative in release_files(root):
        if relative.suffix != ".md":
            continue
        document = root / relative
        for line in visible_lines(document.read_text(encoding="utf-8")):
            # The destination grammar is shared by ordinary links and images.
            linked = re.sub(r"(?<!!)\[([^\]\n]*)\]\(", r"![\1](", line)
            targets, _ = image_targets(linked)
            for target in targets:
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                destination = (document.parent / unquote(parsed.path)).resolve()
                destination.relative_to(root.resolve())
                if not destination.is_file():
                    raise ValueError("Broken local link in " + str(relative) + ": " + target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the existing ZIP without writing")
    args = parser.parse_args()
    destination = ROOT / "dist/thesis-project-writer.zip"
    try:
        expected = make_archive()
        if args.check:
            if not destination.is_file() or destination.read_bytes() != expected:
                raise ValueError("Distribution is stale; run scripts/build_release.py")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(expected)
        verify_links()
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Release verified" if args.check else "Release built and links verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
