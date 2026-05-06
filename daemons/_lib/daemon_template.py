#!/usr/bin/env python3
"""
daemon_template.py — producer-daemon helpers.

Each of the 5 systemd-style daemons (lint / security / performance / gaps /
upgrade) is a slim wrapper that:
  1. Imports its detectors from ./detectors/
  2. Runs them in sequence (or parallel where independent)
  3. Writes a summary JSON to ~/inbox/_summaries/pending/<DATE>/<daemon>_<host>.json
  4. Optionally writes per-finding briefs to ~/inbox/{critical,daily,weekly}/

This template provides the summary contract helpers. Each daemon should emit
the same fields so the collector and any downstream review loop can rank,
route, carry forward, and close findings without guessing.

Customize:
  - DAEMON_NAME = "lint"
  - from .detectors import detector_a, detector_b
  - DETECTORS = (detector_a, detector_b)
  - LOOKING_FOR = "Dead code, broken refs, ..."
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("prism.daemon")

_VALID_PRIORITIES = ("P0", "P1", "P2", "P3")
_DEFAULT_SKILL_BY_DAEMON = {
    "lint": "lint",
    "security": "security",
    "performance": "performance",
    "gaps": "gaps",
    "upgrade": "upskill",
    "debug": "debug",
}
_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def _detect_host() -> str:
    """Resolve host identifier. Override via $PRISM_HOST env var."""
    h = os.environ.get("PRISM_HOST", "").strip()
    if h:
        return h
    return Path.home().name or "local"


def _inbox_root() -> Path:
    """Resolve inbox root. Override via $PRISM_INBOX (used by install.sh smoke test)."""
    override = os.environ.get("PRISM_INBOX", "").strip()
    return Path(override) if override else Path.home() / "inbox"


def _slug(value: str) -> str:
    return "-".join(value.lower().replace("_", "-").split())[:80] or "finding"


def normalize_finding(daemon: str, finding: dict[str, Any]) -> dict[str, Any]:
    """Return one public-safe finding with the standard Prism fields."""
    title = str(finding.get("title") or finding.get("summary") or "Untitled finding")
    affected_surface = str(finding.get("affected_surface") or daemon)
    priority = str(finding.get("priority") or "P3").upper()
    if priority not in _VALID_PRIORITIES:
        priority = "P3"
    confidence = str(finding.get("confidence") or "medium").lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = "medium"
    suggested_next_skill = str(
        finding.get("suggested_next_skill")
        or finding.get("next_skill")
        or _DEFAULT_SKILL_BY_DAEMON.get(daemon, "gaps")
    )
    evidence = finding.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list):
        evidence = [str(evidence)]

    finding_id = str(finding.get("id") or f"{daemon}:{_slug(affected_surface)}:{_slug(title)}")
    return {
        "id": finding_id,
        "title": title,
        "description": str(finding.get("description") or ""),
        "affected_surface": affected_surface,
        "priority": priority,
        "confidence": confidence,
        "suggested_next_skill": suggested_next_skill,
        "evidence": evidence,
        "carry_forward": bool(finding.get("carry_forward", True)),
        "status": str(finding.get("status") or "open"),
    }


def build_proposed_actions(daemon: str, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert findings into ranked next actions for humans or skill loops."""
    actions: list[dict[str, Any]] = []
    for finding in sorted(findings, key=lambda f: (_PRIORITY_RANK.get(f["priority"], 9), f["id"])):
        if finding.get("status") == "resolved":
            continue
        actions.append({
            "finding_id": finding["id"],
            "priority": finding["priority"],
            "suggested_next_skill": finding["suggested_next_skill"],
            "action": f"Run /{finding['suggested_next_skill']} on {finding['affected_surface']}: {finding['title']}",
            "confidence": finding["confidence"],
            "source_daemon": daemon,
        })
    return actions


def build_summary(
    daemon: str,
    looking_for: str,
    findings: list[dict[str, Any]],
    self_report: dict[str, Any],
) -> dict[str, Any]:
    """Build a complete daemon summary using the standard Prism schema."""
    normalized = [normalize_finding(daemon, f) for f in findings]
    return {
        "schema_version": "prism.summary.v2",
        "looking_for": looking_for,
        "findings_count": len(normalized),
        "findings": normalized,
        "proposed_actions": build_proposed_actions(daemon, normalized),
        "finding_lifecycle": {
            "new": 0,
            "recurring": 0,
            "resolved": 0,
            "regressed": 0,
            "carried_forward": 0,
        },
        "self_report": self_report,
    }


def write_summary(daemon: str, host: str, summary: dict[str, Any]) -> Path:
    """
    Write summary JSON to <inbox>/_summaries/pending/<DATE>/<daemon>_<host>.json.
    Returns the path written.
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pending = _inbox_root() / "_summaries" / "pending" / date_str
    pending.mkdir(parents=True, exist_ok=True)
    path = pending / f"{daemon}_{host}.json"
    summary.setdefault("schema_version", "prism.summary.v2")
    summary.setdefault("findings", [])
    summary.setdefault("findings_count", len(summary.get("findings", [])))
    summary.setdefault("proposed_actions", build_proposed_actions(
        daemon,
        [normalize_finding(daemon, f) for f in summary.get("findings", [])],
    ))
    summary.setdefault("finding_lifecycle", {
        "new": 0,
        "recurring": 0,
        "resolved": 0,
        "regressed": 0,
        "carried_forward": 0,
    })
    summary["daemon"] = daemon
    summary["host"] = host
    summary["written_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps(summary, indent=2))
    log.info("summary | written to %s", path)
    return path


def write_heartbeat(daemon: str, host: str, status: str, errors: list[str]) -> None:
    """Write daemon heartbeat marker for liveness checks."""
    hb_dir = _inbox_root() / "_heartbeat"
    hb_dir.mkdir(parents=True, exist_ok=True)
    (hb_dir / f"prism-{daemon}_{host}.json").write_text(json.dumps({
        "daemon": daemon,
        "host": host,
        "status": status,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2))
