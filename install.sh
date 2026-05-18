#!/bin/bash
# install.sh — set up simply-ops-prism locally + (optionally) install LaunchAgent timer.
# Idempotent: re-running this is safe.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
INBOX="${PRISM_INBOX:-$HOME/inbox}"
CACHE="${PRISM_TMPDIR:-$HOME/.cache/simply-ops-prism}"

echo "==> simply-ops-prism local install"
echo "    repo: $REPO_DIR"

# 0. Python 3.10+ preflight
if ! command -v python3 >/dev/null 2>&1; then
    echo "    ✗ python3 not found in PATH. Install Python 3.10+ and retry." >&2
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    echo "    ✗ python3 is older than 3.10. Detected: $(python3 --version 2>&1). Install Python 3.10+ and retry." >&2
    exit 1
fi
echo "    ✓ python3 $(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))') OK"

# 1. Create inbox + cache dirs
mkdir -p "$INBOX/_summaries/pending" "$INBOX/_summaries/ready" "$INBOX/_summaries/consumed"
mkdir -p "$INBOX/_heartbeat" "$INBOX/critical" "$INBOX/daily" "$INBOX/weekly" "$INBOX/archive"
mkdir -p "$CACHE"
echo "    ✓ created $INBOX/* + $CACHE/"

# 2. Smoke-test the chain (dry run, sandboxed inbox so we never touch the user's real ~/inbox)
SMOKE_INBOX="$(mktemp -d -t prism-smoke-XXXXXX)"
SMOKE_TMPDIR="$(mktemp -d -t prism-smoke-tmp-XXXXXX)"
echo "==> smoke test (single run, dry-run on each daemon, PRISM_INBOX=$SMOKE_INBOX)"
if PRISM_INBOX="$SMOKE_INBOX" PRISM_TMPDIR="$SMOKE_TMPDIR" bash "$REPO_DIR/run_parallel.sh"; then
    echo "    ✓ smoke test passed"
    rm -rf "$SMOKE_INBOX" "$SMOKE_TMPDIR"
else
    echo "    ✗ smoke test failed — check $CACHE/simply-ops-prism.log (sandbox kept at $SMOKE_INBOX)"
    exit 1
fi

# 3. Optionally install LaunchAgent (macOS only, opt-in to avoid surprise writes)
if [[ "$(uname)" == "Darwin" ]]; then
    AGENT_SRC="$REPO_DIR/launchd/com.example.simply-ops-prism.plist"
    AGENT_DST="$HOME/Library/LaunchAgents/com.example.simply-ops-prism.plist"
    LABEL="com.example.simply-ops-prism"

    if [[ "${PRISM_INSTALL_LAUNCHAGENT:-0}" != "1" ]]; then
        echo "==> LaunchAgent install skipped"
        echo "    To install later: PRISM_INSTALL_LAUNCHAGENT=1 bash $REPO_DIR/install.sh"
    elif [[ -f "$AGENT_DST" ]]; then
        echo "==> LaunchAgent already installed at $AGENT_DST — skipping (run launchctl unload first to reinstall)"
    else
        mkdir -p "$(dirname "$AGENT_DST")"
        # Substitute placeholders with this clone's actual path before install.
        sed -e "s|/Users/USERNAME/path/to/simply-ops-prism|$REPO_DIR|g" \
            -e "s|/Users/USERNAME|$HOME|g" \
            "$AGENT_SRC" > "$AGENT_DST"
        echo "    wrote $AGENT_DST"
        echo "    To activate: launchctl load -w '$AGENT_DST'"
        echo "    To check:    launchctl print gui/\$(id -u)/$LABEL | grep -E 'state|next fire'"
    fi
fi

# 4. Print next steps
cat <<EOF

==> install complete

Next steps:
  1. Customize daemons/lint/detectors/, daemons/security/detectors/ etc with real logic.
  2. Run on demand:    bash $REPO_DIR/run_parallel.sh
  3. Install timer:     PRISM_INSTALL_LAUNCHAGENT=1 bash $REPO_DIR/install.sh
  4. View summaries:   ls $INBOX/_summaries/pending/\$(date +%Y-%m-%d)/
  5. Read bundle:      cat $INBOX/_summaries/ready/\$(date +%Y-%m-%d)_bundle.json | python3 -m json.tool
  6. Mark consumed:    python3 $REPO_DIR/daemons/_lib/collector.py --consume <bundle_id>

To uninstall:
  launchctl unload "$HOME/Library/LaunchAgents/com.example.simply-ops-prism.plist" 2>/dev/null
  rm "$HOME/Library/LaunchAgents/com.example.simply-ops-prism.plist"
EOF
