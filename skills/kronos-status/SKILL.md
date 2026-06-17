---
name: kronos-status
description: Shows the current state of the KRONOS workflow — which stages are closed, open, or skipped. Color-coded: ✅ closed, ⏳ in progress, ⊘ skipped, ⬜ pending. Used when the user says /kronos-status, /kronos status, "what's the workflow state", "which stages are open", "workflow status".
---

# /kronos-status

Shows the current state of the active KRONOS workflow.

## Algorithm

1. Read `WORKFLOW.md` in the current project (cwd)
2. If it is empty → report: "No active workflow. Run `/kronos-start <task>`."
3. Otherwise print a report:

```
🎯 Workflow: <Task>
   Slug:  <date>-<slug>
   Type:  TRIVIAL | MICRO | MEDIUM | LARGE | OPS
   Started: <ts>

Stages:                         (for OPS: show the ## OPS Checklist sub-steps instead)
  1. PLAN    ✅ done   plans/<slug>.md (62 lines)
  2. CODE    ⏳ in progress   N files staged
  3. TEST    ⬜ pending
  4. DOCS    ⬜ pending
  5. COMMIT  ⬜ pending

Bypasses:  N used  (warns above KRONOS_BYPASS_WARN, default 2)

Latest activity:
  - <ts> CODE: 3 files changed
  - <ts> PLAN done: plans/<slug>.md
  - <ts> kronos-start: workflow created

Next step: /kronos-next  (CODE → TEST transition)
```

The **Bypasses** count = number of `**BYPASS used**` entries in the Decisions log. A count
above `KRONOS_BYPASS_WARN` (default 2) means the task is likely the wrong Type — consider
`OPS` (multi-commit pipeline) or `MICRO` (lightweight increment).

## Extra checks (print AFTER the report, if they fire)

### A. Terminal but un-archived workflow

If **all 5 stages are closed** (each `[x]` or `[⊘]`, none `[ ]`/`[⏳]`), but WORKFLOW.md is
still active (Task non-empty) → this is a "hanging" workflow. It **gates future unrelated
commits**. Print a warning:

```
⚠ Workflow is TERMINAL (all stages closed) but not archived.
  It will block future commits. Archive it:
  mv WORKFLOW.md workflow-archive/<date>-<slug>.md  + reset the template
  (or just say "archive the workflow").
```
Since `/kronos-status` is read-only — **do not archive yourself**, only flag it (archiving is
done by `/kronos-next` step 3 or `/kronos-skip` step 5).

### B. Scope-drift — work outran the workflow

Compare the staged files (`git diff --name-only` + `--cached`, across all managed repos) with
the **declared scope** of the active workflow (slug + the Affected files in `plans/<slug>.md`,
if present). If the staged files are **significantly broader** (other domains/modules, many
times more files, not mentioned in the plan) → print:

```
⚠ Scope-drift: staged changes are broader than workflow "<slug>".
  The work seems to have outrun the current workflow (Type=<T>).
  Consider: close the current one and /kronos-start <new task, Type=LARGE>,
  or Type=OPS (multi-commit pipeline) if it is one large delivery.
```
A heuristic, **not a block** — just a signal. The goal is to catch "a large task rode under
the umbrella of a small/unrelated workflow".

## Color markers (for parsing the checkbox)

| In WORKFLOW.md | What to show |
|---|---|
| `[x]` | ✅ done |
| `[⊘]` | ⊘ skipped (+ reason from the Decisions log) |
| `[⏳]` | ⏳ in progress |
| `[ ]` / `[]` | ⬜ pending |

## What it does NOT do

- Does not modify WORKFLOW.md
- Does not run stages (that's `/kronos-next`)
- Does not block anything

This is a **read-only** command — safe at any time.
