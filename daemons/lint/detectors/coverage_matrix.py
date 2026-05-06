"""
coverage_matrix.py — report-only producer/artifact/daemon/proof coverage check.

This detector is intentionally small and dependency-free. It checks the public
Prism starter matrix at config/coverage_matrix.json unless PRISM_COVERAGE_MATRIX
points elsewhere.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]


def _inbox_root() -> Path:
    override = os.environ.get("PRISM_INBOX", "").strip()
    return Path(override) if override else Path.home() / "inbox"


def _cache_root() -> Path:
    override = os.environ.get("PRISM_TMPDIR", "").strip()
    return Path(override) if override else Path.home() / ".cache" / "simply-ops-prism"


def _matrix_path() -> Path:
    override = os.environ.get("PRISM_COVERAGE_MATRIX", "").strip()
    return Path(override).expanduser() if override else REPO / "config" / "coverage_matrix.json"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _expand(value: str) -> Path:
    rendered = (
        value.replace("{repo}", str(REPO))
        .replace("{inbox}", str(_inbox_root()))
        .replace("{cache}", str(_cache_root()))
        .replace("{date}", _today())
    )
    return Path(rendered).expanduser()


def _load_matrix() -> dict[str, Any]:
    path = _matrix_path()
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _heartbeat_fresh(check: dict[str, Any], max_age_hours: float) -> tuple[bool, str]:
    path = _expand(str(check.get("path") or ""))
    if not path.exists():
        return False, f"heartbeat missing: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"heartbeat unreadable: {path}: {exc}"
    ts = data.get("timestamp") or data.get("ts")
    if not ts:
        return False, f"heartbeat timestamp missing: {path}"
    parsed = _parse_iso(str(ts))
    if parsed is None:
        return False, f"heartbeat timestamp unparsable: {path}: {ts}"
    age_hours = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600
    if age_hours > max_age_hours:
        return False, f"heartbeat stale: {path}: {age_hours:.1f}h"
    if data.get("errors"):
        return False, f"heartbeat reports errors: {path}: {data.get('errors')}"
    return True, f"heartbeat fresh: {path}"


def _check(row: dict[str, Any], check: dict[str, Any], defaults: dict[str, Any]) -> tuple[bool, str]:
    ctype = str(check.get("type") or "")
    path_value = str(check.get("path") or "")
    if ctype == "path_exists":
        path = _expand(path_value)
        return path.exists(), f"path_exists:{path}"
    if ctype == "dir_exists":
        path = _expand(path_value)
        return path.is_dir(), f"dir_exists:{path}"
    if ctype == "heartbeat_fresh":
        max_age = float(check.get("max_age_hours") or defaults.get("heartbeat_max_age_hours") or 36)
        return _heartbeat_fresh(check, max_age)
    return False, f"unknown check type: {ctype}"


def _finding(row: dict[str, Any], evidence: str) -> dict[str, Any]:
    surface = str(row.get("surface") or "unknown")
    return {
        "id": f"coverage:{surface}",
        "title": f"Coverage proof missing for {surface}",
        "description": (
            "A producer -> artifact/state -> expected daemon -> proof row is not currently verified."
        ),
        "affected_surface": surface,
        "priority": "P2" if row.get("protected") else "P3",
        "confidence": "high",
        "suggested_next_skill": "gaps",
        "evidence": [
            f"producer={row.get('producer')}",
            f"artifact_state={row.get('artifact_state')}",
            f"expected_daemon={row.get('expected_daemon')}",
            f"proof_source={row.get('proof_source')}",
            evidence,
        ],
        "carry_forward": True,
        "status": "open",
    }


def run() -> list[dict[str, Any]]:
    matrix = _load_matrix()
    defaults = matrix.get("defaults") or {}
    findings: list[dict[str, Any]] = []
    for row in matrix.get("surfaces") or []:
        if not isinstance(row, dict):
            continue
        checks = row.get("checks") or []
        for check in checks:
            if not isinstance(check, dict):
                continue
            ok, evidence = _check(row, check, defaults)
            if not ok:
                findings.append(_finding(row, evidence))
                break
    return findings
