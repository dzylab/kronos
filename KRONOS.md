# KRONOS Workflow Engine

**Version:** 1.0 (public, 5 stages)
**Purpose:** force every code/documentation change through PLAN → CODE → TEST → DOCS → COMMIT with independent verification, auto-classification, and parallelization.

KRONOS is a git pre-commit guard built on a Claude Code hook (PreToolUse). It does not trust the checkboxes in `WORKFLOW.md` — for every `[x]` stage it independently re-checks the fact (the plan file exists and is large enough, there is a git diff, the test log is non-empty, the documentation really changed, a commit hash is recorded). You cannot fake your way through.

> **Threat model:** KRONOS is a discipline/quality gate against an *honest-but-optimistic* agent, NOT a security boundary against a hostile one. See [THREAT_MODEL.md](THREAT_MODEL.md) for exactly what it does and does not defend against.

---

## Configuration (env variables)

KRONOS is configured through environment variables. See `config.example.yaml` and `install.sh`.

| Variable | Purpose | Default |
|---|---|---|
| `PROJECT_PATH` | Root of the main project (the code repository) | the hook's cwd |
| `VAULT_PATH` | Documentation directory (Obsidian vault / docs / wiki — a separate git repo) | a sibling `vault`/`docs`/`wiki` folder |
| `KRONOS_REPOS` | Extra repositories to check for a diff (submodules etc.), comma-separated | empty |
| `KRONOS_BYPASS` | `1` to bypass the gate (recorded in the Decisions log) | unset |
| `KRONOS_LOG_TZ_OFFSET` | Timezone offset (hours) for Decisions-log timestamps | `0` (UTC) |

`~` and `$VAR` are supported in paths.

---

## Repository architecture

KRONOS works with **1–N local git repositories**:

| Role | From | What |
|---|---|---|
| **Main project** | `cwd` (where `WORKFLOW.md` lives) | the application code |
| **Extra repo** (optional) | `KRONOS_REPOS` | submodules, separate modules |
| **Docs vault** (optional) | `VAULT_PATH` | a separate repo with notes/docs |

The **CODE** `[x]` stage is valid if **at least one** of these repositories has a `git diff` (staged or unstaged). See `verify_code()` in `hooks/check-workflow.py`.

### Git — everything local

All git operations (`status`/`diff`/`commit`/`push`) happen **locally**. If deploy targets a remote server, files get there via `scp`/`rsync`/CI, **bypassing git on the server**. No `git commit` is done on prod.

### Submodule gotcha

If the main project uses a submodule, `git status` in the parent will only show `modified: <submodule> (modified content)` without specific files when files inside the submodule change. That is normal. For details: `cd <submodule> && git status`.

---

## The 5 stages

| # | Stage | Hard "done [x]" criterion | What the hook checks |
|---|---|---|---|
| 1 | **PLAN** | `plans/<slug>.md` exists AND `wc -l >= 50` | file and line count |
| 2 | **CODE** | `git diff` non-empty; no TS/lint errors | `git diff --cached` or `git diff` non-empty in any repo |
| 3 | **TEST** | the `## Test log` section in `WORKFLOW.md` has >= 5 lines of real output | lines in the section |
| 4 | **DOCS** | the `## Docs updated` section lists files + `git status VAULT_PATH` shows modified | parses the list, checks the vault diff |
| 5 | **COMMIT** | a git hash (7+ hex) in the `WORKFLOW.md` Activity log | regex search for hex |

**The hook does INDEPENDENT verification** — it does NOT trust the `[x]` checkboxes, it always checks facts. A forged `[x]` without confirmation → BLOCK exit 2.

**⊘ skipped** — a stage marked skipped via `/kronos-skip`. The hook accepts it as closed but requires a "SKIPPED stage X: <reason>" entry in the Decisions log.

---

## 3 task categories (auto-classify)

`/kronos-start` automatically determines the Type:

### TRIVIAL — 3 stages (CODE → DOCS → COMMIT)
- Conditions: diff <= 10 lines, 1 file, **not on a critical path** (auth, permissions, migrations, etc. — tunable per project)
- Examples: typo in a comment, a small string edit, a version bump
- **PLAN and TEST are skipped** via `/kronos-skip` with reason "TRIVIAL"
- **0 parallel explore agents**

### MEDIUM — 5 stages, 2 parallel
- Conditions: 1 module, > 10 lines, 2-3 files
- Examples: a new endpoint, a new page, a config + UI change
- **2 parallel explore agents on PLAN**
- **2 parallel checks on TEST**

### LARGE — 5 stages, max parallelism
- Conditions: several modules (backend + frontend + migration + docs)
- Examples: a large new feature, a DB migration with UI, a big refactor
- **5 parallel explore agents on PLAN**
- **2-3 parallel agents on CODE** (by layer)
- **3 parallel checks on TEST**

---

## Documentation Routing — 3 mechanisms

The DOCS stage uses these **in sequence**:

### 1. Routing Table (`KRONOS-ROUTING.md`)
A static map of "file X changed → update document Y". Instant. Covers ~80% of cases. **Maintained by hand** — when you add a new module, **in the same CODE stage** add a line to `KRONOS-ROUTING.md`. Template: `KRONOS-ROUTING.example.md`.

### 2. Discovery Agent (`/kronos-find-docs`)
Takes `git diff --name-only`, extracts keys (function names, endpoints, classes), and `Grep`s the vault for those keys. Finds files not covered by the Routing Table. 10-15 s.

### 3. Sanity Check (`/kronos-sanity-check`)
**BEFORE** moving from DOCS to COMMIT. Compares PUBLIC changes in the code (new endpoints, models, pages, permissions) against what actually changed in the vault. If PUBLIC changes are **not** reflected → it flags "maybe forgotten: X, Y, Z" and DOCS returns to ⏳ open.

---

## Smart Parallelism — table by stage

| Stage | TRIVIAL | MEDIUM | LARGE |
|---|---|---|---|
| **PLAN** | ⊘ skip | 2 explore agents | 5 explore agents |
| **CODE** | main | main | 2-3 parallel by layer |
| **TEST** | ⊘ skip ("TRIVIAL") | 2 parallel checks | 3 parallel |
| **DOCS** | find-docs + 1 agent | find-docs + N agents | same |
| **COMMIT** | git commit + push | git commit + push | parallel push to N repos |

### Reserved-for-orchestrator contract

When CODE fans out to parallel agents, the risk is simple: **changes that converge into one file**. Two agents editing the same file race and clobber each other. The contract:

- **Parallel agents get only leaf files** — disjoint file sets, no shared file between any two agents.
- **Convergence points are edited serially by the orchestrator** (the main loop), never by a fan-out agent. The usual convergence points:
  - i18n / translation bundles (every feature appends keys to the same files)
  - navigation config / router tables (every page registers itself)
  - barrel exports (`index.ts` and friends — every module re-exports through one file)
  - lock files (`package-lock.json`, `poetry.lock`, etc.)
  - the migration head / `alembic` revision pointer (one head, serialized)
  - `WORKFLOW.md` itself

This is a **contract, not enforcement** — the hook does not police it. For genuinely shared zones that must be touched in parallel, give each agent `isolation: "worktree"` so they edit isolated copies and you merge afterward.

---

## Watchdog (stuck-task detection)

The watchdog is a **cross-cutting liveness mechanism**, NOT a sixth stage. The pipeline stays **PLAN → CODE → TEST → DOCS → COMMIT**; the watchdog runs *during* long stages (typically CODE/TEST: a build, a background Bash job, an external agent/server) and checks whether the stage is alive. Command: `/kronos-watchdog`.

### Principle: a PROGRESS detector, not a timeout

The cardinal rule: **do not kill honest long-running tasks.** The watchdog judges by whether the **progress signal changes** (an output file grows, a new log line / new layer appears, the process is alive, an endpoint responds), not by a bare timeout. A long but progressing operation is normal and is left alone. A dumb timeout without a progress check causes false positives and is forbidden here.

### STALLED is judged from the PROBE, not from HEARTBEAT

The STALLED verdict is computed from the **last time the watchdog itself observed the PROBE change** — an objective signal the watchdog reads on every tick and logs to the Activity log. It is **not** computed from `HEARTBEAT`.

`HEARTBEAT` is an **advisory**, agent-written marker. The same agent that might declare a stage done prematurely also writes HEARTBEAT, so it is the most forgeable signal and is never the source of truth for STALLED.

**Forgeability gradient** — when several progress signals exist, trust the least forgeable one:

```
process exit code  >  file CONTENT change  >  size/mtime growth   >>   agent HEARTBEAT
   (hard fact)         (hard to fake)          (cheap: `touch`)          (advisory — NOT for STALLED)
```

There is **no perfect progress signal**. The watchdog is a *heuristic early warning*, not proof of liveness; when signals disagree or are missing it fails toward caution — worst case the commit gate stays closed rather than letting a dead stage pass as done.

**Observer ≠ observed.** The watchdog is an independent observer (a persistent `Monitor`, or `/loop`) that reads only *external* signals about the observed process. It is not part of that process and cannot be silenced by it: a hung process cannot make the watchdog report "ALIVE"; at worst it goes quiet, which reads as a frozen probe → STALLED.

### Heartbeat model

An active long stage has a `## Heartbeat` section in `WORKFLOW.md` (fields from `WORKFLOW.template.md`):

```
- STAGE:     CODE
- STARTED:   2026-01-15T18:00:00+0000   # when the stage started
- HEARTBEAT: 2026-01-15T18:12:00+0000   # (advisory) last progress the agent noted — NOT used for STALLED
- SLA_SOFT:  30                          # soft threshold (min)
- SLA_HARD:  60                          # hard threshold (min)
- PROBE:     build.log grows / process state R|S
```

SLA defaults by Type (soft/hard, minutes): **TRIVIAL 5/10, MEDIUM 15/30, LARGE 30/60** (`SLA_HARD = 2 x SLA_SOFT`).

### States and thresholds

| Verdict | Condition (basis = last observed PROBE change) | Action |
|---|---|---|
| 🟢 **ALIVE** | the probe changed (signal grew/changed) | log the observation; stage healthy |
| 🟡 **SLOW** | `now − last_probe_change > SLA_SOFT`, but some progress remains | log the probe, keep observing (do not panic) |
| 🔴 **STALLED** | `now − last_probe_change > SLA_HARD` AND the probe is frozen | mark `⚠️STALLED`, notify, propose **retry** / `/kronos-skip` / manual intervention |

Every verdict is written as a line in `## Activity log` (traceability), including the observed probe value.

### Periodic polling: event-driven vs timer

While a long stage is active there are two "periodic polling" mechanisms:

1. **Event-driven (preferred for background jobs):** a persistent **Monitor** on a completion/error marker in the output file → wake up IMMEDIATELY on the event, no polling delay.
2. **Timer fallback (safety net):** `/loop 10m /kronos-watchdog` OR `ScheduleWakeup` at 600–1200 s — fires on the timer even if the event never arrives.

Best practice is **both**: the Monitor catches the event instantly; the timer covers the case where the process died quietly and the EOF marker / event never appeared. Do not rely on the timer alone (slow to react) or the event alone (it may never come).

### Boundaries

The watchdog **observes, flags, and proposes** — it does not kill processes and does not edit code. The decision (retry / skip / kill) belongs to a human or the main agent. Watchdog edits are confined to `WORKFLOW.md` (Heartbeat + Activity log) — read-mostly.

### Relationship to the hook (HARD)

The hook (`check-workflow.py`) does a **hard** extra check at `git commit`: if the workflow uses a heartbeat (a `## Heartbeat` section exists) and at least one stage is `[x]`, but WORKFLOW.md has no `STARTED` trace (timestamp) → the commit is **BLOCKED** (exit 2). You cannot quietly mark "done" a stage that never started. Exemptions (commit still passes): the PLAN stage (auto-started by workflow creation and already gated by `verify_plan` — the plan artifact must be ≥ `MIN_PLAN_LINES` — so a separate trace is redundant), a workflow without a `## Heartbeat` section (legacy, backward-compatible), stages marked `[⊘]`/`[ ]`/`[⏳]` (no trace required), and `KRONOS_BYPASS=1`. The existing hard checks are untouched.

---

## Escape hatch: `KRONOS_BYPASS=1`

```bash
KRONOS_BYPASS=1 git commit -m "hotfix: critical prod down"
```

The hook passes + automatically appends an entry to the Decisions log:
```
- 2026-01-01T12:00:00+00:00 **BYPASS used**, command: `git commit -m hotfix`
```

Used for:
- Critical production hotfixes
- Mechanical commits (version bumps, date updates, typos)
- When KRONOS itself is broken

**Every bypass is visible in the Decisions log** — accountability is preserved.

---

## Auto-recovery after an agent restart

**First action in any new session:**
```bash
cat WORKFLOW.md
```

If the file is non-empty and has an open stage — continue from it via `/kronos-next`. If empty — wait for a task.

**Template state = there is NO active workflow.** After a workflow completes, the file is reset to the `WORKFLOW.template.md` template: the Task field is a `<...>` placeholder (or empty), stages are `[ ]`. The hook recognizes this (by the angle-bracket pattern, language-agnostic) and **does not block** the commit — otherwise the reset template would be misread as an "active unfinished workflow" and would block any commit.

Protection against an interrupted session (power loss, terminal closed) — `WORKFLOW.md` keeps its open stage, and a new session picks it up.

---

## Commands (slash skills)

| Command | Purpose |
|---|---|
| `/kronos-start <name>` | Start a workflow. Plan agent + Type auto-classification. |
| `/kronos-next` | The next open stage. With Type-based parallelism. |
| `/kronos-route` | **CODE orchestration layer.** Reads the plan → domain→specialist-agent→model tier, decides parallel/pipeline, size-gate (TRIVIAL 0 / MEDIUM ≤2 / LARGE ≤5). Mode `KRONOS_ROUTE_MODE` (**confirm-multi** default): auto when <=1 agent; when **>=2 agents** or a critical path → show the dispatch + cost-saving options (Run as-is / Just 1 / I'll do it / Cancel). The hook does NOT execute it — the main loop does. |
| `/kronos-status` | Shows the current workflow's checkboxes with colors (✅ ⏳ ⊘ [ ]). |
| `/kronos-skip <stage> <reason>` | Mark a stage ⊘ + an entry in the Decisions log. |
| `/kronos-find-docs` | Routing Table + Discovery Agent → list of files for DOCS. |
| `/kronos-sanity-check` | Pre-COMMIT check: PUBLIC code changes vs the vault. |
| `/kronos-watchdog` | Cross-cutting stuck-task detector: probes progress of an active long stage (see Watchdog). |

---

## Archive of completed workflows

After all 5 stages close — `WORKFLOW.md` → `workflow-archive/<date>-<slug>.md`, and `WORKFLOW.md` is reset to the template (`WORKFLOW.template.md`).

---

## Install

```bash
git clone <repo> kronos
cd kronos
cp config.example.yaml config.yaml   # fill in PROJECT_PATH, VAULT_PATH
./install.sh                          # copies hooks/ and skills/ into ~/.claude/
```

Then register the hook in `~/.claude/settings.json` (see README).

---

## Related files

- `~/.claude/settings.json` — PreToolUse hook registration
- `hooks/check-workflow.{sh,py}` — the hook (matcher Bash|PowerShell)
- `THREAT_MODEL.md` — what KRONOS does and does not defend against
- `KRONOS-ROUTING.example.md` — template of the static code→docs map
- `skills/kronos-*/SKILL.md` — 7 slash commands
- `WORKFLOW.template.md` — the active-workflow template
- `<project>/WORKFLOW.md` — the current active workflow
- `<project>/plans/<slug>.md` — plans
- `<project>/workflow-archive/<date>-<slug>.md` — history
