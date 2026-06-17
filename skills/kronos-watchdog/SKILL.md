---
name: kronos-watchdog
description: Stuck-task detector (WATCHDOG) for KRONOS. Checks whether the current long stage is ALIVE — distinguishes "still working" (progress) from "stuck" (progress frozen longer than SLA_HARD). It looks at PROGRESS observed from objective probes (an output file growing, a live process, a responsive endpoint), not at a timeout. Invoked when the user says /kronos-watchdog, periodically via /loop, or when a long operation (build, background Bash job, external agent/server) has gone quiet and it is unclear whether it is "working or dead".
---

# /kronos-watchdog

**A cross-cutting stuck-task guard.** This is NOT a linear "6th stage" — the pipeline stays
**PLAN → CODE → TEST → DOCS → COMMIT**. The watchdog is a *cross-cutting* progress check that
runs DURING long stages (CODE/TEST: a build, a background Bash job, an external agent/server).
Read-mostly: it observes, logs, flags STALLED, and **proposes** actions — but it never kills
anything itself and never edits the project's code.

## Principle: a PROGRESS detector, not a timeout

The watchdog looks at whether the **signal changes** (an output file's size/mtime, the last log
line, a counter, a process state), not just how much time has passed. **A long but progressing
task must NOT be touched.** A false positive on an honest long operation is a watchdog bug, not a
"success".

## STALLED is judged from the PROBE, not from HEARTBEAT

The STALLED verdict is computed from the **last time the watchdog itself observed the PROBE
change** — an objective signal the watchdog reads on every tick and logs to the Activity log.
It is **not** computed from `HEARTBEAT`.

`HEARTBEAT` is an **advisory**, agent-written marker. The same agent that might prematurely
declare a stage done also writes HEARTBEAT, so it is the most forgeable signal and is never the
source of truth for STALLED.

### Forgeability gradient — prefer the least forgeable signal

When several progress signals are available, trust the least forgeable one:

```
process exit code  >  file CONTENT change  >  size/mtime growth   >>   agent HEARTBEAT
   (hard fact)         (hard to fake)          (cheap to fake by         (advisory only —
                                                e.g. `touch`)             NOT for STALLED)
```

There is **no perfect progress signal**. The watchdog is a *heuristic early warning*, not a
proof of liveness. When signals disagree or are missing, fail toward caution — worst case the
gate stays closed (the commit is blocked) rather than letting a dead stage pass as done.

### Observer ≠ observed

The watchdog is an **independent observer** (a persistent `Monitor`, or `/loop`) that reads only
**external** signals about the observed process — it is not part of that process and cannot be
silenced by it. A hung or hostile process cannot make the watchdog report "ALIVE"; at worst it
goes quiet, which the watchdog reads as a frozen probe → STALLED.

## Heartbeat model (the `## Heartbeat` section of WORKFLOW.md)

```
- STAGE:     CODE
- STARTED:   2026-01-15T18:00:00+0000   # when the stage started
- HEARTBEAT: 2026-01-15T18:12:00+0000   # (advisory) last progress the AGENT noted — NOT used for STALLED
- SLA_SOFT:  30                          # soft threshold (min) → probe/observe
- SLA_HARD:  60                          # hard threshold (min) → STALLED
- PROBE:     build.log grows / process state R|S
```

SLA defaults by Type (soft/hard, minutes): **TRIVIAL 5/10, MEDIUM 15/30, LARGE 30/60**
(`SLA_HARD = 2 x SLA_SOFT`). The person who starts the long stage fills these fields in; the
field template is in `WORKFLOW.template.md`.

## Algorithm

### 1. Read the active stage
`cat WORKFLOW.md` → the `## Heartbeat` section (STAGE / STARTED / HEARTBEAT / SLA_SOFT /
SLA_HARD / PROBE). If the section is missing, empty, or `STAGE: -` → there is no active long
stage: report "nothing to guard" and exit (this is not an error).

### 2. Run the progress PROBE (per the PROBE field)
Generic probes (pick the one that matches PROBE), in order of decreasing trust:

- **Process exit / state:** has the process exited (and with what code)? Otherwise its state —
  `R`/`S` (alive) vs `D` (uninterruptible) / `Z` (zombie), CPU/IO != 0. e.g. `ps -o stat,%cpu,etimes -p <pid>`.
- **Output file CONTENT change:** has the *content* (not just mtime) changed since the last
  probe — a new log line, a new build step/layer? Compare a hash/tail with the last value.
- **Output file size/mtime growth:** did `wc -c <output>` / `ls -la <output>` grow since the
  last probe? (Cheapest, most forgeable — corroborate with content when possible.)
- **External endpoint / agent / queue:** a light liveness ping or status re-query —
  `curl -s -o /dev/null -w '%{http_code}' --max-time 3 <health-url>`.

Every probe is read-only: do not restart or kill the task at this step. Record the observed
probe value in the Activity log so the next tick can compare against it.

### 3. Verdict (now = current time; basis = last observed PROBE change)
- 🟢 **ALIVE** — the probe changed since last tick (progress) → log the observation; the stage
  is healthy. (HEARTBEAT may also be refreshed, but it is advisory only.)
- 🟡 **SLOW** — `now − last_probe_change > SLA_SOFT`, but there is still some progress → log the
  probe, keep observing (do NOT panic, do NOT propose a kill).
- 🔴 **STALLED** — `now − last_probe_change > SLA_HARD` AND the probe is frozen → mark the stage
  `⚠️STALLED`, notify the user, and **propose** one of: **retry** / `/kronos-skip <N> <reason>` /
  manual intervention.

### 4. Log the verdict in the Activity log (traceability)
Every verdict → a line in `## Activity log` of WORKFLOW.md, including the observed probe value:
```
- 2026-01-15T18:24:00+0000 watchdog 🟢 ALIVE: build.log 2.1MB→3.4MB (CODE)
- 2026-01-15T18:40:00+0000 watchdog 🟡 SLOW: build.log growing slowly, 18min since last change (CODE)
- 2026-01-15T18:55:00+0000 watchdog 🔴 STALLED: build.log frozen 35min, process state D (CODE)
```

## Periodic polling (event-driven vs timer)

While a long stage is active there are two paths (more in `KRONOS.md`, Watchdog section):

1. **Event-driven (preferred for background jobs):** a persistent **Monitor** on a
   completion/error marker in the output file → you wake up IMMEDIATELY on the event.
2. **Timer fallback (safety net):** `/loop 10m /kronos-watchdog` OR `ScheduleWakeup` at 600–1200 s.

Best practice is **both**: the Monitor catches the event instantly; the timer covers the case
where the event never arrives (the process died quietly, the output stopped without an EOF
marker). Do not rely on the timer alone (it reacts with delay), and do not rely on the event
alone (it may never come).

## What the watchdog does NOT do (boundaries)

- ❌ It does not kill processes itself and does not edit the project's code — it only observes and **proposes**.
- ❌ It does not apply a dumb timeout without checking progress (that causes false positives on honest long operations).
- ✅ The decision (retry / skip / kill) belongs to a human or the main agent.
- It only edits `WORKFLOW.md` (Heartbeat / Activity log) — read-mostly.

## Relationship to the hook

The hook (`hooks/check-workflow.py`) does a **HARD** check at `git commit`: if the workflow uses
a heartbeat (a `## Heartbeat` section exists) and at least one stage is `[x]`, but WORKFLOW.md
has no `STARTED` trace (timestamp) → the commit is **BLOCKED** (exit 2). The goal: you cannot
quietly mark "done" a stage that never started. Exemptions (commit still passes): the PLAN stage
(auto-started by workflow creation and already gated by `verify_plan`'s plan artifact, so a separate
trace is redundant), a workflow without a `## Heartbeat` section (legacy, fully backward-compatible),
stages marked `[⊘]`/`[ ]`/`[⏳]` (no trace required), and `KRONOS_BYPASS=1`. The existing hard checks are untouched.
