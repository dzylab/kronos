---
name: kronos-next
description: Advance the KRONOS workflow to the next open stage (5 stages: PLAN/CODE/TEST/DOCS/COMMIT). Uses Smart Parallelism by Type (TRIVIAL=0 explore, MEDIUM=2, LARGE=5). Used when the user says /kronos-next, /kronos next, or asks to continue the active workflow. After each stage it verifies the criterion ITSELF and marks [x] only if the fact is confirmed.
---

# /kronos-next

Runs the next open stage of the active KRONOS workflow, with parallelism by Type.

## Algorithm

### 1. Read WORKFLOW.md

- If empty → error "No active workflow. Run /kronos-start <task>."
- Find the first stage that is `[ ]` or `[⏳]`
- Note the `Type` from the header — it drives parallelism

### 2. Heartbeat discipline (watchdog)

**On ENTERING any stage** — update the `## Heartbeat` section of WORKFLOW.md:
```
- STAGE:     <stage name>
- STARTED:   <now ISO>
- HEARTBEAT: <now ISO>
- SLA_SOFT:  <TRIVIAL 5 / MEDIUM 15 / LARGE 30>
- SLA_HARD:  <2x SLA_SOFT>
- PROBE:     <how to measure progress of this stage>
```
And append to the Activity log: `STAGE <NAME> STARTED at <now>`. This gives the hook a STARTED trace —
without it, a `[x]` stage of a heartbeat workflow (EXCEPT PLAN) BLOCKS the commit (exit 2, Phase B hard-gate).
PLAN is exempt (it is auto-started by workflow creation and gated by `verify_plan`'s artifact).

**On each real progress step** — update `HEARTBEAT: <now>`.

**If a stage launches a LONG operation** (build, background job, external agent/server):
- arm a **Monitor** (`persistent: true`) on a completion/error marker in the output file, AND
- periodically `/kronos-watchdog` (via `/loop 10m` or `ScheduleWakeup` 600-1200s).
- The watchdog tells 🟢ALIVE / 🟡SLOW / 🔴STALLED by PROGRESS. Do NOT treat the task as dead
  until the watchdog says 🔴STALLED.

### 3. Smart Parallelism — what to do at each stage

#### Stage 1: PLAN
Check: `plans/<slug>.md` exists and `wc -l >= 50`.
- If **TRIVIAL** → `/kronos-skip 1 TRIVIAL task` (skip PLAN)
- If it exists and is >= 50 lines → `[x]`, log "PLAN done: plans/<slug>.md (N lines)"
- If not — CREATE the plan via a Plan agent (as in /kronos-start step 3)
  - **MEDIUM:** 2 parallel `Explore` agents for context
  - **LARGE:** 5 parallel `Explore` agents
- Then — **ask the user to sign off on the plan** before `[x]`

#### Stage 2: CODE
**Step 0 (if Type != TRIVIAL) — `/kronos-code-standards`:** loads the code canon (Clean Code + style
guides + your project rules), writes a STANDARDS block to the Activity log. The code agents (route §7)
receive it in their instructions. No STANDARDS.md → built-in defaults (does not fail). Guidance only — no block.

**Then — dispatch via `/kronos-route`** (the orchestration layer: domain -> agent -> model):
- **TRIVIAL:** the router is skipped → the main loop makes the edits itself (Edit/Write sequentially).
- **MEDIUM/LARGE:** invoke `/kronos-route`. It reads the plan ("Affected files"), maps domains to
  specialist agents with model tiers (backend->`backend-agent`, frontend->`frontend-agent`, etc.),
  decides parallel/pipeline and the mode (`KRONOS_ROUTE_MODE`, default `confirm-multi`):
  - `exec=auto` (clear domains, no critical path) → execute the dispatch via `Workflow`/`Agent`.
  - `exec=await` (critical path: auth/permissions/migrations/security guards, OR ambiguous) →
    show the dispatch to the user, wait for sign-off, then execute.
  - The dispatch is ALWAYS written to the Activity log (`route: …`) — transparency.
- Each agent edits ONLY its own files; shared files (locale/i18n) go to one agent or a final synthesis phase.
- `git add` the relevant files
- Stage `[x]` when: `git diff --cached --quiet` exits 1 (there is staged content)
- Activity log entry: "CODE done: N files changed, +X/-Y lines"

**⚠️ Critical:** if you add a new module (a new API/page file) — **immediately** add a line to `KRONOS-ROUTING.md` (so routing does not go stale).

#### Stage 3: TEST
Run checks on the result:
- **TRIVIAL** → `/kronos-skip 3 TRIVIAL task`
- **MEDIUM:** 2 parallel checks (e.g. call the endpoint + inspect the log)
- **LARGE:** 3 parallel (backend check + frontend smoke + DB query)

Paste the output of each check **into the '## Test log' section** of WORKFLOW.md. The hook requires >= 5 lines of real output.

`[x]` when the Test log section is filled. Activity log entry: "TEST done: N checks, all PASS".

#### Stage 4: DOCS
The trickiest stage — 4 routing mechanisms:

0. **`/kronos-doc-standards`** (if Type != TRIVIAL) — loads the doc canon (Diataxis + density + frontmatter), classifies the target files by type, writes a DOC-STANDARDS block to the Activity log. The parallel doc agents (step 2) receive it. Guidance only — no block.
1. **`/kronos-find-docs`** — Routing Table lookup + Discovery Agent (Grep). Returns the list of documentation files to update.
2. **Parallel agents** — one per file, each updating a single file (Edit operations, not Write).
3. **`/kronos-sanity-check`** — compares the project diff vs the vault diff. If PUBLIC changes (new endpoints/models/pages) are not reflected — it flags them and DOCS returns to `⏳`.

Fill the **'## Docs updated'** section with the list of updated files (one per line, path from the vault root). The hook checks that `git status VAULT_PATH` shows changes.

`[x]` when the sanity check passes.

#### Stage 5: COMMIT
- `git commit -m "<message>"` with a meaningful message (type prefix: `feat:` / `fix:` / `docs:` / `chore:`)
- Record the hash from `git log -1 --format=%H` in the Activity log
- Push:
  - **TRIVIAL/MEDIUM:** sequential push to the current repo (if a remote exists)
  - **LARGE:** **parallel push** to all repos (project + vault + submodules)
- If there is no remote → an entry in the Decisions log: "no remote configured, push skipped"

`[x]` when the hash is recorded.

### 4. After all 5 stages are [x] / [⊘]

- Archive: `mv WORKFLOW.md workflow-archive/<date>-<slug>.md`
- Restore WORKFLOW.md from the template (`WORKFLOW.template.md`)
- Tell the user: the workflow is complete, the archive is here
- Optional: create a record in the vault history / session journal

### 5. NEVER mark `[x]` without verifying the fact

The hook verifies independently:
- PLAN [x] → plans/<slug>.md >= 50 lines
- CODE [x] → there is a staged/unstaged diff
- TEST [x] → Test log >= 5 lines
- DOCS [x] → vault modified + Docs updated non-empty
- COMMIT [x] → hex hash in WORKFLOW.md

If you lie — the hook returns exit 2 and the commit is cancelled. An honest `[ ]` + a blocker note is better.

## If a stage did not work out

- Leave `[ ]` or change it to `[⏳]` (in progress)
- Write the concrete reason in the Activity log: "CODE: blocked by failing test X, needs investigation"
- Tell the user what is needed to move forward
- If it really will not work — `/kronos-skip <stage> <reason>` (⊘ + an entry in Decisions)

## What it does NOT do

- Does not run backups/destructive operations automatically
- Does not skip stages without a reason (only TRIVIAL for PLAN/TEST)
