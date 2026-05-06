# simply-ops-prism

**Sprawl wins by inches.** One stale package this week. One drifted config next. One silently dead cron the week after.

**Six scouts. One report. Sprawl loses.**

```bash
curl -fsSL https://raw.githubusercontent.com/nardovibecoding/simply-ops-prism/main/install.sh | bash
```

After: six daemons (lint, security, performance, gaps, upgrade, debug) fire in parallel once a day, write findings into your local inbox, and a collector assembles one bundle you read on coffee. One orchestrator chain, one host x daemon matrix, one ranked action queue.

**Platform**: macOS + Linux. Requires Python 3.10+. LaunchAgent integration is
macOS-only; Linux users can wire the same `run_parallel.sh` to a `systemd --user`
timer or a cron entry.

---

## What this is

`simply-ops-prism` is the chain shape behind a daily multi-axis self-audit:

1. **6 producer daemons** scan different surfaces — lint, security,
   performance, gaps, upgrade, debug.
2. **One orchestrator** (`run_parallel.sh`) fires them in parallel, waits,
   then assembles a single bundle.
3. **You** read the bundle once a day, approve/defer/skip findings,
   get back to building.

The point isn't the specific detectors — those you write for *your* stack.
The point is the **pipeline shape**:

- **One timer, not three.** No coincidence-scheduling between rsync,
  collector, and producers. One chain, no race window.
- **One finding contract.** Every daemon uses the same fields: evidence,
  affected surface, priority, confidence, suggested next skill, and
  carry-forward.
- **One matrix.** The bundle shows each host and each daemon as ready or
  missing, with counts and top priority.
- **Bundles consume → briefs auto-archive.** No 300-file inbox by Friday.
- **Heartbeats + done-marker.** Silent failures show up loud the next morning.

---

## Quickstart

```bash
git clone https://github.com/<your-user>/simply-ops-prism.git
cd simply-ops-prism
bash install.sh
```

The installer:
- Creates `~/inbox/{_summaries,_heartbeat,critical,daily,weekly,archive}/`
- Runs a smoke test (all 6 daemons fire in dry-run mode)
- On macOS, drops a LaunchAgent template you can `launchctl load` to schedule
  daily 14:00 fires

## Manual run

```bash
bash run_parallel.sh
```

Outputs to `~/.cache/simply-ops-prism/simply-ops-prism.log`. The chain ends with a done-marker
at `~/.cache/simply-ops-prism/parallel_done.<DATE>`.

## Read today's bundle

```bash
cat ~/inbox/_summaries/ready/$(date +%Y-%m-%d)_bundle.json | python3 -m json.tool
```

## Mark a bundle consumed (auto-archives its briefs)

```bash
python3 daemons/_lib/collector.py --consume <bundle_id>
```

---

## Directory layout

```
simply-ops-prism/
├── run_parallel.sh             # orchestrator — 6 daemons → collector → done-marker
├── install.sh                  # idempotent installer
├── daemons/
│   ├── _lib/
│   │   ├── collector.py        # bundles summaries, archives briefs on consume
│   │   └── daemon_template.py  # write_summary + write_heartbeat helpers
│   ├── lint/      detectors/   # write your detectors here
│   ├── security/  detectors/
│   ├── performance/ detectors/
│   ├── gaps/      detectors/
│   ├── upgrade/   detectors/
│   └── debug_scan.py           # 6th producer, inline (no separate daemon)
├── launchd/
│   └── com.example.simply-ops-prism.plist  # macOS LaunchAgent template
└── examples/                   # detector examples (TBD)
```

## Customization knobs

| Setting | Where | Default |
|---|---|---|
| schedule | `launchd/com.example.simply-ops-prism.plist` Hour/Minute | 14:00 |
| timezone | `PRISM_TZ` env in plist or `~/.simply-ops-prism.env` | `UTC` |
| daemon detectors | `daemons/<daemon>/detectors/*.py` | empty stubs |
| host name | `PRISM_HOST` env, else `Path.home().name` | (your username) |
| collector hosts | `PRISM_HOSTS=mac,hel,london` on the collector host | current host only |
| inbox root | `PRISM_INBOX` env (used by smoke test for sandbox) | `~/inbox` |
| cache + log dir | `PRISM_TMPDIR` env (used by smoke test for sandbox) | `~/.cache/simply-ops-prism` |
| min summaries to bundle | `PRISM_MIN_SUMMARIES` or `--min N` flag on collector | 6 |

## Finding schema

Detector modules should return plain dictionaries. The daemon helper normalizes
them into this public contract:

```json
{
  "id": "security:ssh-policy:password-login-enabled",
  "title": "Password login is enabled",
  "description": "Short explanation of what changed or why it matters.",
  "affected_surface": "ssh",
  "priority": "P1",
  "confidence": "high",
  "suggested_next_skill": "security",
  "evidence": ["config:sshd_config"],
  "carry_forward": true,
  "status": "open"
}
```

The collector adds:

- `finding_lifecycle`: new, recurring, resolved, regressed, carried-forward.
- `matrix`: host x daemon readiness and top priority.
- `action_queue`: ranked next actions, grouped across every daemon and host.

Routing is intentionally generic:

| Finding type | Suggested next skill |
|---|---|
| unclear root cause, blocked command, drift | `debug` |
| secrets, permissions, risky automation | `security` |
| slow scan, cost, queue pressure | `performance` |
| stale docs, schema drift, broken references | `lint` |
| better process or detector opportunity | `upskill` |
| concrete accepted file change | `ship` |
| missing coverage, contradictions, unowned item | `gaps` |

---

## Why one timer, not three

This template was extracted after a real race condition: a separate timer for
parallel-fire, another for VPS-rsync, another for collect — the three would
schedule-coincide and the bundle would freeze with 8/18 entries instead of 18/18.

The fix: **one timer fires `run_parallel.sh` once daily.** Inside the script,
the 6 daemons run in parallel, then `wait`, then collector assembles. No
separate timers means no race possible. If you add more producers, add them to
the `run_parallel.sh` chain — never to a separate timer.

## Multi-host

For multi-host (laptop + servers): set `PRISM_HOST=<name>` on each producer
host, set `PRISM_HOSTS=laptop,server1,server2` on the collector host, and copy
remote pending summaries into the collector inbox before the collector step in
`run_parallel.sh`.

Your final bundle then has all `6 x N` host entries. If one host misses a day,
the matrix shows that gap and prior unresolved findings can carry forward.

This repo keeps the transport generic on purpose. Use whichever copy method is
normal for your environment, then keep the collector contract stable.

---

## License

MIT — see `LICENSE`.

## Credits

Pattern extracted from a solo builder's daily-ops stack. The discipline
(single-orchestrator chain, producer-consumer declaration, auto-archive on
consume) is generic; the implementation is yours.
