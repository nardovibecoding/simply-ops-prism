#!/usr/bin/env python3
"""
daemon_template.py — minimal producer-daemon skeleton.

Each of the 5 systemd-style daemons (lint / security / performance / gaps /
upgrade) is a slim wrapper that:
  1. Imports its detectors from ./detectors/
  2. Runs them in sequence (or parallel where independent)
  3. Writes a summary JSON to ~/inbox/_summaries/pending/<DATE>/<daemon>_<host>.json
  4. Optionally writes per-finding briefs to ~/inbox/{critical,daily,weekly}/

This template provides the write_summary helper. Each daemon.py copies the
pattern below and replaces the detector list.

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


def write_summary(daemon: str, host: str, summary: dict[str, Any]) -> Path:
    """
    Write summary JSON to <inbox>/_summaries/pending/<DATE>/<daemon>_<host>.json.
    Returns the path written.
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pending = _inbox_root() / "_summaries" / "pending" / date_str
    pending.mkdir(parents=True, exist_ok=True)
    path = pending / f"{daemon}_{host}.json"
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
