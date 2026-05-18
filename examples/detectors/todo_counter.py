"""Example read-only detector for simply-ops-prism.

Copy this file into `daemons/lint/detectors/` to try the plugin shape.
It scans the repo for TODO markers while skipping runtime and VCS directories.
"""
from pathlib import Path


SKIP_DIRS = {".git", "__pycache__", ".ruff_cache", ".venv", "node_modules"}


def run():
    repo = Path(__file__).resolve().parents[3]
    hits = []
    for path in sorted(repo.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix not in {".py", ".md", ".sh", ".json", ".plist"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        count = text.count("TODO")
        if count:
            hits.append(f"{path.relative_to(repo)}:{count}")

    if not hits:
        return []

    return [{
        "id": "lint:example:todo-counter",
        "title": "Example detector found TODO markers",
        "description": "Replace this example with checks that matter for your stack.",
        "affected_surface": "source-tree",
        "priority": "P3",
        "confidence": "medium",
        "suggested_next_skill": "lint",
        "evidence": hits[:10],
        "carry_forward": True,
        "status": "open",
    }]
