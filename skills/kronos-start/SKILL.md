---
name: kronos-start
description: Start a new KRONOS workflow with automatic Type classification (TRIVIAL/MEDIUM/LARGE). Creates plans/<date>-<slug>.md, fills WORKFLOW.md, and for MEDIUM/LARGE launches parallel explore agents for context. Used when the user says /kronos-start, /kronos start, or asks to begin a new task with a workflow. The agent calls this command ITSELF before any code/doc change.
---

# /kronos-start <task name>

Initializes a new KRONOS workflow in the current project.

## Usage

```
/kronos-start Refactor auth layer to support SSO
```

or just `/kronos-start` (then ask the user for the name).

## Algorithm

### 1. Check that WORKFLOW.md is not busy

`cat WORKFLOW.md` — if there is a `Task: <non-empty>` OR an open stage `[ ]`/`[⏳]`:
> **STOP** with the message: "A workflow `<task>` is already active. Close it first (`/kronos-next` to the end) or clear it manually (mv WORKFLOW.md → workflow-archive/, restore the template from WORKFLOW.template.md)."

### 2. Build a slug

- Convert the name to kebab-case ASCII (non-ASCII → transliterate, spaces → `-`, lowercase, `[a-z0-9-]`)
- Prefix with the date: `<YYYY-MM-DD>-<slug>` → `2026-01-15-refactor-auth-layer`

### 3. Create `plans/<date>-<slug>.md` (>= 50 lines)

Launch a Plan agent (`subagent_type=Plan`) with the task description. The Plan agent returns a plan with sections:
- Context (what exists now)
- Goal (what should exist)
- Steps (step by step)
- Affected files (list of touched files — critical for Type classification)
- Risks
- Acceptance criteria
- Out of scope

Save to `plans/<date>-<slug>.md`. Check `wc -l >= 50` — otherwise add detail in Risks/Out of scope.

### 4. AUTO-CLASSIFY Type

Determine Type from the plan + context:

**TRIVIAL** (3 stages CODE → DOCS → COMMIT, PLAN and TEST ⊘):
- All conditions at once:
  - Affected files: exactly 1
  - Diff will be <= 10 lines
  - The file is **NOT on a critical path** (tune this for your project — e.g. auth, permissions, DB migrations, security guards)
- Examples: typo in a comment, typo in a localization string, version bump

**LARGE** (5 stages + max parallelism):
- Affected files: 3+ modules touched (backend + frontend, or backend + migration + docs, etc.)
- Examples: a large new feature, a DB migration with UI, a big refactor

**MEDIUM** (5 stages, 2 parallel) — the default:
- 1 module (backend only, or frontend only, or docs only)
- 2-3 files touched

**MICRO** (PLAN 1-line + TEST + COMMIT):
- A quick test increment that still needs tracking, where a 50-line plan is overkill
- `verify_plan` accepts a 1-line plan for MICRO; TEST is required (correctness gate)
- Pairs with the branch-gate so quick feature-branch commits don't slip past the gate

**OPS** (multi-commit pipeline — deploy / release):
- Many intermediate commits (test→drift→stage→merge→deploy→smoke)
- Use an `## OPS Checklist` of sub-steps instead of the 5 stages; each commit closes one
  sub-step (no bypass). An `[x]` sub-step must carry a trace (hash/PASSED/done).

### 5. Fill WORKFLOW.md

Copy from `WORKFLOW.template.md` and fill in the header:

```markdown
# Active Workflow

**Task:** <name>
**Started:** <ISO timestamp>
**Slug:** <date>-<slug>
**Type:** TRIVIAL | MEDIUM | LARGE

## Stages (5 stages)

- [ ] 1. **PLAN** → `plans/<slug>.md` >= 50 lines + user sign-off
- [ ] 2. **CODE** → `git diff` is non-empty, no TS/lint errors
- [ ] 3. **TEST** → the '## Test log' section below has >= 5 lines of real output
- [ ] 4. **DOCS** → the '## Docs updated' section + `git status VAULT_PATH` confirms
- [ ] 5. **COMMIT** → commit hash in the Activity log + push

## Heartbeat (watchdog — current ⏳ stage)

<!-- /kronos-next fills this on entering a stage. HARD-gate (Phase B): a [x] stage
     (except PLAN) without a "STAGE <NAME> STARTED" trace → commit is BLOCKED. -->

- STAGE:     -
- STARTED:   -
- HEARTBEAT: -
- SLA_SOFT:  <TRIVIAL 5 / MEDIUM 15 / LARGE 30>
- SLA_HARD:  <2x SLA_SOFT>
- PROBE:     -

## Test log

## Docs updated

## Activity log

- <ts> **kronos-start**: workflow created, slug=<slug>, Type=<TYPE>, plan: plans/<date>-<slug>.md (<N> lines)

## Decisions log
```

### 6. Mark PLAN right away

- If the plan file is >= 50 lines → `[x]` + an Activity log entry
- If **Type=TRIVIAL** → `[⊘]` + a "SKIPPED stage 1: TRIVIAL task" entry in the Decisions log
- Otherwise → `[ ]` + an entry noting the reason

### 7. For MEDIUM/LARGE — launch explore agents IN PARALLEL for context

- **MEDIUM:** 2 parallel `Explore` agents (e.g. "study the current structure of X", "find similar changes in history")
- **LARGE:** 5 parallel `Explore` agents (backend module, frontend module, DB, config, precedents)
- TRIVIAL: 0 agents (plan + straight to CODE)

Add the results to the "Context found" section of `plans/<date>-<slug>.md`.

### 8. Report to the user

- Workflow created, slug
- Type auto-classified: TRIVIAL/MEDIUM/LARGE (with justification)
- Path to the plan
- Sign-off: **"the plan is ready, shall we proceed?"** (PLAN [x] needs sign-off)
- Next step: `/kronos-next` for CODE

## If something breaks

- The Plan agent did not start → create a minimal plan by hand (>= 50 lines of structure with TODOs) and warn
- `plans/` does not exist → `mkdir plans` first
- Explore agents failed → continue with what you have, record "explore failed" in Decisions
