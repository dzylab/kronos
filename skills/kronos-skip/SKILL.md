---
name: kronos-skip
description: Skip a stage of the KRONOS workflow with a mandatory reason. Marks the stage as ⊘ skipped + records the reason in the Decisions log. Used when the user says /kronos-skip <N> <reason>, or when you need to skip TEST/DOCS for a TRIVIAL task.
---

# /kronos-skip <stage_number> <reason>

Skips the given stage of the active workflow.

## Usage

```
/kronos-skip 3 TRIVIAL task — no point testing a typo
/kronos-skip 4 docs already updated in a previous commit
/kronos-skip 1 hotfix — skip planning, go straight to the fix
```

## Algorithm

### 1. Validation
- WORKFLOW.md exists and is non-empty → otherwise error "no active workflow"
- `stage_number` is 1-5
- The reason (after the number) is non-empty and meaningful (>= 5 words or an explicit keyword like TRIVIAL/hotfix)

### 2. Find the stage in WORKFLOW.md

Regex `^\- \[.\] <N>\. \*\*(PLAN|CODE|TEST|DOCS|COMMIT)\*\*`. If it is already `[x]` (done) → error "stage already closed". If `[⊘]` → error "stage already skipped".

### 3. Change `[ ]` → `[⊘]` via Edit

```python
# In WORKFLOW.md:
# - [ ] 3. **TEST** → ...
# becomes:
# - [⊘] 3. **TEST** → ...
```

### 4. Record in the Decisions log + Activity log

```markdown
## Decisions log

- 2026-01-15T18:30:00+00:00 **SKIPPED stage 3 (TEST)**: TRIVIAL task — no point testing a typo
```

And in the Activity log:
```markdown
- 2026-01-15T18:30:00+00:00 **kronos-skip**: stage 3 TEST skipped (TRIVIAL task)
```

### 5. Report to the user

- Stage N (X) marked ⊘ skipped
- Reason: <reason>
- Next step: `/kronos-next` to move to the next open stage

## IMPORTANT — the hook accepts ⊘ as closed only with a record

`hooks/check-workflow.py` checks: if a stage is `[⊘]`, there must be a `SKIPPED stage N` or `skipped <name>` entry in the Decisions log. Otherwise → BLOCK exit 2.

So **always record the reason** through this command; do not edit the checkbox by hand.

## Typical reasons to skip

- **TRIVIAL task** — PLAN and TEST for typos, version bumps
- **hotfix** — emergency prod fix, document after the fact
- **docs already updated in a previous commit** — DOCS already done
- **manual verification done** — TEST checked by eye instead of automation
- **handover** — another context will continue, state is being passed on

## What it does NOT do

- Does not mark `[x]` (this is not done, it is skipped)
- Does not run destructive operations
- Does not close the whole workflow — the other stages still need to be closed/skipped
