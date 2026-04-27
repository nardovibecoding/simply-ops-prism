#!/usr/bin/env python3
"""
upgrade/daemon.py — minimal example. Replace detectors with real logic.

Run: python3 daemons/upgrade/daemon.py --dry-run
"""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "_lib"))
from daemon_template import write_summary, write_heartbeat, _detect_host

DAEMON = "upgrade"
LOOKING_FOR = {
    "lint": "Dead code, broken refs, fallback chains.",
    "security": "Exposed credentials, SSH policy, vuln packages.",
    "performance": "Context growth, cache misses, host metrics.",
    "gaps": "SPREAD/SHRINK gaps, phantom infra, deploy post-flight.",
    "upgrade": "Outdated tools, packages, external intelligence.",
}.get(DAEMON, "")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    host = _detect_host()
    findings: list[dict] = []  # populate by running detectors
    summary = {
        "looking_for": LOOKING_FOR,
        "findings_count": len(findings),
        "proposed_actions": [],
        "self_report": {"daemon_health": "green", "dry_run": args.dry_run},
    }
    write_summary(DAEMON, host, summary)
    write_heartbeat(DAEMON, host, "ok", errors=[])
    print(f"[{DAEMON}] cycle done | findings={len(findings)}")


if __name__ == "__main__":
    main()
