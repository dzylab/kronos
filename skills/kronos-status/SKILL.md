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
   Type:  TRIVIAL | MEDIUM | LARGE
   Started: <ts>

Stages:
  1. PLAN    ✅ done   plans/<slug>.md (62 lines)
  2. CODE    ⏳ in progress   N files staged
  3. TEST    ⬜ pending
  4. DOCS    ⬜ pending
  5. COMMIT  ⬜ pending

Latest activity:
  - <ts> CODE: 3 files changed
  - <ts> PLAN done: plans/<slug>.md
  - <ts> kronos-start: workflow created

Next step: /kronos-next  (CODE → TEST transition)
```

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
