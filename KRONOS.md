# KRONOS Workflow Engine

**Version:** 1.5.0 (public, 5 stages + OPS/MICRO + standards layer + vault-commit exemption + lifecycle hygiene; 1.5.0 — optional web-project STANDARDS example; 1.4.0 — "disciplined repo" README section; 1.3.0 — design-principles guidance in the standards layer; 1.2.1 — Windows OSError hardening in the commit hook)
**Purpose:** force every code/documentation change through PLAN → CODE → TEST → DOCS → COMMIT with independent verification, auto-classification, and parallelization.

KRONOS is a git pre-commit guard built on a Claude Code hook (PreToolUse). It does not trust the checkboxes in `WORKFLOW.md` — for every `[x]` stage it independently re-checks the fact (the plan file exists and is large enough, there is a git diff, the test log is non-empty, the documentation really changed, a commit hash is recorded). You cannot fake your way through.

> **Threat model:** KRONOS is a discipline/quality gate against an *honest-but-optimistic* agent, NOT a security boundary against a hostile one. See [THREAT_MODEL.md](THREAT_MODEL.md) for exactly what it does and does not defend against.

---

## Configuration (env variables)

KRONOS is configured through environment variables. See `config.example.yaml` and `install.sh`.

| Variable | Purpose | Default |
|---|---|---|
| `PROJECT_PATH` | Project root override (repo with `WORKFLOW.md`); set only for a monorepo or when git runs from a subdirectory — otherwise the hook uses its cwd | the hook's cwd |
| `VAULT_PATH` | Documentation directory (Obsidian vault / docs / wiki — a separate git repo) | a sibling `vault`/`docs`/`wiki` folder |
| `KRONOS_REPOS` | Extra repositories to check for a diff (submodules etc.), comma-separated | empty |
| `KRONOS_BYPASS` | `1` to bypass the gate (recorded in the Decisions log) | unset |
| `KRONOS_LOG_TZ_OFFSET` | Timezone offset (hours) for Decisions-log timestamps | `0` (UTC) |
| `KRONOS_BRANCH_GATE` | `0` disables the branch-gate (block real code on a non-default branch with no workflow) | `1` (on) |
| `KRONOS_BYPASS_WARN` | Bypass count per workflow above which the hook warns | `2` |
| `KRONOS_TEST_PASS_MARKERS` | Comma-separated success markers for the TEST gate | `ALL CHECKS PASSED,PASSED,passed,OK` |
| `KRONOS_TEST_FAIL_MARKERS` | Comma-separated failure markers for the TEST gate | `FAILED,Traceback (most recent call last)` |

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

## 5 task types (auto-classify)

`/kronos-start` automatically determines the Type. Besides TRIVIAL/MEDIUM/LARGE there are **MICRO** (a lightweight increment) and **OPS** (a multi-commit pipeline).

### Which type when

| Type | When | Stages | Gate note |
|---|---|---|---|
| **TRIVIAL** | 1 file, <=10 lines, not a critical path | CODE→DOCS→COMMIT (PLAN/TEST ⊘) | — |
| **MICRO** | a quick test increment that still needs tracking | PLAN(1 line)+TEST+COMMIT | `verify_plan` drops the 50-line floor (MICRO → >=1) |
| **MEDIUM** | 1 module, 2-3 files (default) | 5, 2 parallel | — |
| **LARGE** | several modules / migration + UI | 5, max parallelism | — |
| **OPS** | deploy/release/multi-step pipeline with N commits | `## OPS Checklist` (test→drift→stage→merge→deploy→smoke) | each commit closes a sub-step; passes without bypass; an `[x]` step without a trace → BLOCK |

### TRIVIAL — 3 stages (CODE → DOCS → COMMIT)
- Conditions: diff <= 10 lines, 1 file, **not on a critical path** (auth, permissions, migrations, etc. — tunable per project)
- Examples: typo in a comment, a small string edit, a version bump
- **PLAN and TEST are skipped** via `/kronos-skip` with reason "TRIVIAL"
- **0 parallel explore agents**

### MICRO — lightweight increment (PLAN + TEST + COMMIT)
- Conditions: a quick fix / test increment that needs tracking, where a 50-line plan is overkill
- The plan is **1 line** (what + why): `verify_plan` for MICRO requires >=1 line, not 50
- **TEST is required** (the correctness gate catches failures) — CODE/DOCS may be `/kronos-skip`ped
- Together with the branch-gate, this closes the "empty template = no gate" gap on feature/test branches

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

### OPS — multi-commit pipeline (deploy / release)
- Conditions: an ops pipeline with N intermediate commits (test→drift-audit→stage→merge→deploy→smoke)
- Instead of "5 stages = 1 commit" — an `## OPS Checklist` of sub-steps; **each closed step = its own commit**, hash in the Activity log
- The hook (`verify_ops`) **ALLOWS** the commit (multi-commit by design), but an `[x]` sub-step without a trace (hash / PASSED / done) → **BLOCK** (you cannot tick a step you did not do)
- Goal: deploy/release goes **THROUGH** the gate, not via `KRONOS_BYPASS` on every commit

```markdown
## OPS Checklist
- [x] test   → pytest 30/30 PASSED (a1b2c3d)
- [x] drift  → orphan audit clean (e4f5061)
- [⏳] deploy → in progress
- [ ] smoke
```

---

## New gates (correctness, branch, bypass-audit)

- **Correctness TEST-gate.** `TEST[x]` now requires REAL green output: it blocks if the Test log has `N failed` / `FAILED` / `Traceback`, **or** has no success marker (`N passed` / `PASSED` / `ALL CHECKS PASSED` / `OK`). Configurable via `KRONOS_TEST_PASS_MARKERS` / `KRONOS_TEST_FAIL_MARKERS`. This catches bugs, not formatting; `/kronos-verify` prepares the artifact.
- **Branch-gate (default-ON).** Committing real code on a NON-default branch with NO active workflow → BLOCK, with a hint to start a workflow (MICRO is fine). Disable via `KRONOS_BRANCH_GATE=0`.
- **Bypass audit.** The hook counts `KRONOS_BYPASS` uses per workflow; above `KRONOS_BYPASS_WARN` (default 2) it warns "bypassed often → consider OPS/MICRO". `/kronos-status` shows the count.
- **Vault/docs-commit exemption (cross-repo).** A `git commit` whose **target repo is the documentation vault** (`VAULT_PATH`) is **never gated** by the code workflow — the vault is the DOCS-stage product, not code under the 5-stage gate. The hook resolves the commit's target git-toplevel (from a leading `cd <path>` / `git -C <path>`, else the tool cwd) and exempts it **only** when it equals the vault's git-toplevel. Every code repo (project root / submodules) stays gated exactly as before. This fixes the surprise where `cd <vault> && git commit` of docs was blocked by an unrelated active code workflow (the hook keys `WORKFLOW.md` off the tool cwd = project root).

## Workflow lifecycle hygiene (skills)

- **Deferred COMMIT ≠ skipped.** `[⊘]` means "never"; a merely *deferred* commit (later / waiting for approval) must leave `COMMIT [ ]` open — the hook already passes an open COMMIT right before `git commit`. `/kronos-skip` refuses a deferral-reason skip of stage 5 and explains. This stops a "closed but never committed" workflow from lingering.
- **Terminal auto-archive.** When the *last* open stage is closed via `/kronos-skip` (not `/kronos-next`), the skill now checks "all 5 stages closed → archive immediately" (same as `/kronos-next` step 3), so a terminal workflow never hangs around gating future unrelated commits. `/kronos-status` flags a terminal-but-un-archived workflow (read-only).
- **Scope-drift signal.** `/kronos-status` warns (does not block) when staged changes are much broader than the active workflow's declared scope — catching "a large task rode under the umbrella of a small/unrelated workflow"; suggests `Type=LARGE` or `OPS`.

---

## Standards layer — code & doc quality

Two skills steer **HOW** to do the work well (the hook checks that work happened, not that it is good —
so this is a **guidance layer, NOT a gate**):

- **`/kronos-code-standards`** (before CODE, Type != TRIVIAL) — loads the **Clean Code** canon + per-
  language style guides + your project rules, and writes a STANDARDS block that the code agents
  (`/kronos-route §7`) receive in their instructions. Optional linter — advisory.
- **`/kronos-doc-standards`** (before DOCS, Type != TRIVIAL) — loads the **Diataxis** canon (tutorial/
  how-to/reference/explanation) + density + frontmatter, classifies the docs by type, and writes a DOC
  block for the doc agents. Optional frontmatter/link checks — advisory.

**Standards source:** env `KRONOS_STANDARDS_PATH` → `<project>/STANDARDS.md` → `~/.claude/STANDARDS.md`
→ built-in defaults (no file → it does not fail, backward-compat). Copy `STANDARDS.example.md` to
`STANDARDS.md` and edit. Keep project-specifics in your own project instructions.

🔴 **Honest boundary:** "write like a veteran / no filler" is guidance (not machine-verifiable). Real
teeth (a linter for code) are advisory in this version; a future `KRONOS_LINT_GATE` flag could route the
linter output into the Test log → the existing correctness gate. The real gates are unchanged.

---

## Parallel workflows (git worktree)

One slot: exactly **one `WORKFLOW.md` per working directory** (the hook reads `cwd/WORKFLOW.md`;
`/kronos-start` STOPs if the slot is occupied). To run **several threads at once**, do not stack slots
in one folder — give each thread its own working copy via `git worktree`:

```bash
# Thread B next to the main one, on its own branch:
git worktree add ../proj-featureB featureB
cd ../proj-featureB
/kronos-start <task B>        # its own WORKFLOW.md, its own branch, an independent slot
```

- `WORKFLOW.md` is git-ignored → each worktree has **its own, independent** copy; no conflict.
- The hook in each worktree checks **its** `WORKFLOW.md` (keyed on cwd) → threads don't interfere, and
  the branch-gate in each one sees an active workflow and won't force a bypass.
- Done with a thread → `git worktree remove ../proj-featureB`. The main thread is untouched.
- This is an honest multitasking quick-win **with no engine change**. Named in-folder slots
  (`.kronos/active/<slug>.md`) would be a larger, separate task — not done yet.

> **Multi-repo (cross-repo):** a fresh repo gets its own `WORKFLOW.md` (Type=MICRO is fine) OR set
> `KRONOS_BRANCH_GATE=0` for it. A "parent governs submodules" hierarchy is NOT supported yet. **DOCS:**
> the gate expects changes under `VAULT_PATH` (a separate repo); docs that live inside the code repo
> (`<repo>/docs/`) are NOT counted by the stock `verify_docs` yet.

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
| `/kronos-verify` | Runs the test oracle + pytest, summarizes, and fills the `## Test log` with a green/red artifact for the correctness TEST-gate. |
| `/kronos-code-standards` | **Code standards (before CODE).** Loads Clean Code + style guides + project rules, writes a STANDARDS block for the code agents (route §7). Guidance only — no block. |
| `/kronos-doc-standards` | **Doc standards (before DOCS).** Loads Diataxis + density + frontmatter, classifies docs by type, writes a DOC block for the doc agents. Guidance only — no block. |

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
- `skills/kronos-*/SKILL.md` — 11 slash commands
- `STANDARDS.example.md` — code (Clean Code) and doc (Diataxis) canons for the standards skills
- `WORKFLOW.template.md` — the active-workflow template
- `<project>/WORKFLOW.md` — the current active workflow
- `<project>/plans/<slug>.md` — plans
- `<project>/workflow-archive/<date>-<slug>.md` — history
