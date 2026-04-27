#!/usr/bin/env python3
"""
collector.py — simply-ops-prism Summary Collector (local-only template variant).

Polls ~/inbox/_summaries/pending/<DATE>/ for daemon summaries.
When 6 (or --min N) summaries are present, assembles a bundle into
~/inbox/_summaries/ready/<date>_bundle.json.

Subcommands:
  --watch [--once] [--min N] [--grace-min M]
      Poll pending dir. --once = single check then exit.
  --consume <bundle_id>
      Move ready/ → consumed/ + archive briefs referenced by this bundle's date.
  --rotate
      Move consumed/*.json older than 30d → archive/*.json.gz.

Local-only: 6 daemons × 1 host = 6 expected summaries.
For multi-host, override _HOSTS and re-run.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def _inbox_root() -> Path:
    """Resolve inbox root. Override via $PRISM_INBOX (used by install.sh smoke test)."""
    import os as _os
    override = _os.environ.get("PRISM_INBOX", "").strip()
    return Path(override) if override else Path.home() / "inbox"


_INBOX_SUMMARIES = _inbox_root() / "_summaries"
_PENDING_BASE = _INBOX_SUMMARIES / "pending"
_READY_DIR = _INBOX_SUMMARIES / "ready"
_CONSUMED_DIR = _INBOX_SUMMARIES / "consumed"
_LOCK_FILE = _INBOX_SUMMARIES / "_collector.lock"

# ---------------------------------------------------------------------------
# Daemon × host matrix — local default = 1 host, override for multi-host.
# ---------------------------------------------------------------------------
_DAEMONS = ("lint", "security", "performance", "gaps", "upgrade", "debug")
_HOSTS = (Path.home().name or "local",)  # single-host default
EXPECTED_KEYS = [f"{d}@{h}" for h in _HOSTS for d in _DAEMONS]
EXPECTED_COUNT = len(EXPECTED_KEYS)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [collector] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
log = logging.getLogger("collector")


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _pending_dir(date_str: str) -> Path:
    return _PENDING_BASE / date_str


def _key_from_filename(fname: str) -> str | None:
    """<daemon>_<host>.json → <daemon>@<host>"""
    stem = fname.removesuffix(".json")
    parts = stem.rsplit("_", 1)
    if len(parts) != 2:
        return None
    daemon, host = parts
    if daemon not in _DAEMONS:
        return None
    return f"{daemon}@{host}"


def _load_summaries(pending_dir: Path) -> dict[str, dict | None]:
    result: dict[str, dict | None] = {}
    if not pending_dir.exists():
        return result
    for fpath in sorted(pending_dir.glob("*.json")):
        key = _key_from_filename(fpath.name)
        if key is None:
            continue
        try:
            result[key] = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("cannot read %s: %s", fpath.name, exc)
            result[key] = None
    return result


def _assemble_bundle(date_str: str, loaded: dict[str, dict | None]) -> dict:
    assembled_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bundle_id = f"{date_str}_{assembled_at[-8:].replace(':', '')}"

    present = {k for k, v in loaded.items() if v is not None}
    missing = [k for k in EXPECTED_KEYS if k not in present]

    summaries: dict[str, Any] = {k: v for k, v in loaded.items() if v is not None}

    return {
        "bundle_id": bundle_id,
        "date": date_str,
        "assembled_at": assembled_at,
        "summaries_count": len(summaries),
        "summaries_missing": missing,
        "summaries": summaries,
    }


def cmd_watch(once: bool, min_count: int, grace_min: int, poll_sec: int) -> None:
    _READY_DIR.mkdir(parents=True, exist_ok=True)
    _LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    while True:
        date_str = _today_str()
        pending_dir = _pending_dir(date_str)
        loaded = _load_summaries(pending_dir)
        valid = sum(1 for v in loaded.values() if v is not None)
        log.info("watch: %d valid summaries in %s (need %d)", valid, pending_dir, min_count)

        ready_path = _READY_DIR / f"{date_str}_bundle.json"
        if valid >= min_count and not ready_path.exists():
            with open(_LOCK_FILE, "w") as lockf:
                fcntl.flock(lockf, fcntl.LOCK_EX)
                bundle = _assemble_bundle(date_str, loaded)
                ready_path.write_text(json.dumps(bundle, indent=2))
                log.info("bundle written: %s (%d summaries, %d missing)",
                         ready_path.name, bundle["summaries_count"],
                         len(bundle["summaries_missing"]))

        if once:
            return
        time.sleep(poll_sec)


def cmd_consume(bundle_id: str) -> None:
    """Move ready/ → consumed/ + archive briefs referenced by date."""
    _CONSUMED_DIR.mkdir(parents=True, exist_ok=True)
    date_str = bundle_id[:10]
    ready_path = _READY_DIR / f"{date_str}_bundle.json"
    if not ready_path.exists():
        log.error("consume: bundle not found at %s", ready_path)
        sys.exit(1)

    bundle = json.loads(ready_path.read_text(encoding="utf-8"))
    if bundle.get("bundle_id") != bundle_id:
        log.error("consume: bundle_id mismatch: file=%s expected=%s",
                  bundle.get("bundle_id"), bundle_id)
        sys.exit(1)

    consumed_path = _CONSUMED_DIR / f"{date_str}_bundle.json"
    ready_path.rename(consumed_path)
    log.info("consume: moved %s → %s", ready_path.name, consumed_path)

    # Clean up pending sources
    pending_dir = _pending_dir(date_str)
    removed = 0
    if pending_dir.exists():
        for f in list(pending_dir.glob("*.json")):
            try:
                f.unlink()
                removed += 1
            except Exception as exc:
                log.warning("could not remove %s: %s", f.name, exc)
    log.info("consume: cleaned %d pending file(s)", removed)

    # Archive briefs referenced by this bundle's date.
    # Patterns: <daemon>_<host>_<DATE>_<rand>.json (per-finding)
    #           prism-<daemon>-<DATE>.md (per-daemon rollup)
    archive_root = _inbox_root() / "archive" / date_str[:7]
    archive_root.mkdir(parents=True, exist_ok=True)
    archived = 0
    for tier in ("critical", "daily", "weekly"):
        tier_dir = _inbox_root() / tier
        if not tier_dir.exists():
            continue
        for brief in list(tier_dir.glob(f"*{date_str}*.json")) + \
                     list(tier_dir.glob(f"*{date_str}*.md")):
            try:
                brief.rename(archive_root / brief.name)
                archived += 1
            except Exception:
                pass
    log.info("consume: archived %d brief(s) for %s", archived, date_str)


def main() -> None:
    p = argparse.ArgumentParser(description="simply-ops-prism summary collector (local)")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--once", action="store_true")
    p.add_argument("--min", type=int, default=EXPECTED_COUNT)
    p.add_argument("--grace-min", type=int, default=60)
    p.add_argument("--poll-sec", type=int, default=60)
    p.add_argument("--consume", metavar="BUNDLE_ID")
    args = p.parse_args()

    if args.consume:
        cmd_consume(args.consume)
        return
    if args.watch:
        cmd_watch(args.once, args.min, args.grace_min, args.poll_sec)
        return
    p.print_help()


if __name__ == "__main__":
    main()
