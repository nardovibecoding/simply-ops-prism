#!/bin/bash
# run_parallel.sh — fire all 6 producer daemons in parallel, then assemble bundle.
# Local single-host pipeline (no VPS sync). For multi-host, fork and add rsync step.
#
# Daemons (canonical order, matches daemons/_lib/collector.py:_DAEMONS):
#   lint → security → performance → gaps → upgrade → debug
# 5 are systemd-style daemon.py modules; debug is invoked inline as a CLI scan.
#
# Usage:
#   bash run_parallel.sh                # normal run

set -u
export TZ="${PRISM_TZ:-UTC}"   # adjust to your local TZ in ~/.simply-ops-prism.env

PRISM_TMP="${PRISM_TMPDIR:-$HOME/.cache/simply-ops-prism}"
mkdir -p "$PRISM_TMP"
LOG="$PRISM_TMP/simply-ops-prism.log"
STATE="$PRISM_TMP/rescan.state"
DATE=$(date +%Y-%m-%d)
INBOX="${PRISM_INBOX:-$HOME/inbox}"
PENDING=$INBOX/_summaries/pending/$DATE


mkdir -p "$PENDING"
> "$STATE"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
trap 'log "interrupted — state at $STATE"; exit 130' INT TERM

log "=== run_parallel start ==="

# Resolve script root so daemons can be located regardless of PWD.
HERE="$(cd "$(dirname "$0")" && pwd)"

run_daemon() {
    local d=$1
    local extra_flags="${2:-}"
    local start
    start=$(date +%s)
    log "  [start] $d"
    if python3 "$HERE/daemons/$d/daemon.py" --dry-run $extra_flags >> "$LOG" 2>&1; then
        local dur=$(( $(date +%s) - start ))
        log "  [ok]    $d (${dur}s)"
        echo "$d ok $dur" >> "$STATE"
    else
        local code=$?
        log "  [ERR]   $d (exit $code)"
        echo "$d err $code" >> "$STATE"
    fi
}

# 6th daemon (debug): runs as inline CLI scan, not a daemon module.
run_daemon_debug() {
    local start
    start=$(date +%s)
    log "  [start] debug"
    if python3 "$HERE/daemons/debug_scan.py" >> "$LOG" 2>&1; then
        local dur=$(( $(date +%s) - start ))
        log "  [ok]    debug (${dur}s)"
        echo "debug ok $dur" >> "$STATE"
    else
        local code=$?
        log "  [ERR]   debug (exit $code)"
        echo "debug err $code" >> "$STATE"
    fi
}

# Step 1/3: launch all 6 in parallel
run_daemon lint        ""             &
run_daemon security    ""             &
run_daemon performance ""             &
run_daemon gaps        ""             &
run_daemon upgrade     ""             &
run_daemon_debug                       &
wait
log "=== all daemons done ==="
log "summaries: $(ls "$PENDING" 2>/dev/null | tr '\n' ' ')"

# Step 2/3: assemble bundle (no VPS rsync — local-only template).
log "=== [2/3] collector start ==="
if python3 "$HERE/daemons/_lib/collector.py" --watch --once --min 6 --grace-min 0 >> "$LOG" 2>&1; then
    log "=== [2/3] collector done OK ==="
else
    log "=== [2/3] collector exit=$? — see log ==="
fi

# Step 3/3: done-marker — read by downstream consumers to confirm
# the chain ran in sequence (not three independent timers racing).
DONE_MARKER="$PRISM_TMP/parallel_done.$DATE"
date -u +%FT%TZ > "$DONE_MARKER"
log "=== [3/3] done-marker written: $DONE_MARKER ==="
log "=== run_parallel done ==="
