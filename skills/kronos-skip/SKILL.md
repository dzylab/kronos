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

### 2b. Special case — the COMMIT stage (5): deferred ≠ skipped

`[⊘]` means **"never"**, not **"later"**. A common mistake: the commit is only **deferred**
(commit later, waiting for approval, not now) and gets marked `[⊘]`. That creates **drift**:
the workflow is logically "closed" but no commit exists, and the file lingers as active,
**gating future unrelated commits** in this and other repos.

**Rule:**
- **Commit is DEFERRED** (will happen later) → **do NOT skip**. Leave `COMMIT [ ]` open.
  The hook **already lets an open COMMIT pass right before `git commit`** (`STAGES_OPTIONAL_BEFORE_COMMIT`)
  — deferral needs no skip, and when you commit, `/kronos-next` closes it and **auto-archives**.
- **Commit will NEVER happen** (experiment discarded, work goes into a different commit/repo,
  task cancelled) → a `[⊘]` skip is **legitimate**, with an explicit reason of that kind.

**If asked to `/kronos-skip 5 <deferral-reason>`** (reason looks like "for now / later / not yet /
defer / waiting / blocked on approval") → **refuse + explain**: "That is a deferral, not a
cancellation. Leaving COMMIT `[ ]` open — the workflow closes and archives automatically on the
real `git commit`. If the commit truly will not happen, re-run with a cancellation reason
(experiment discarded / goes into another commit)."

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

### 5. Terminal check — auto-archive (do NOT leave it hanging!)

After marking `[⊘]`, re-read all 5 stages. **If ALL are closed** (each `[x]` or `[⊘]`, none
`[ ]`/`[⏳]`) → the workflow is **terminal** and must be **archived immediately** (same logic as
`/kronos-next` step 3), otherwise it lingers as active and gates future unrelated commits:

- `mv WORKFLOW.md workflow-archive/<date>-<slug>.md`
- Restore WORKFLOW.md from the template (Task = `(none)`)
- Report: "workflow terminal (all stages closed) → archived".

⚠️ If COMMIT is still `[ ]` (deferral, see 2b) — the workflow is **NOT** terminal, do **NOT** archive.

### 6. Report to the user

- Stage N (X) marked ⊘ skipped
- Reason: <reason>
- If archived (step 5) → say so; otherwise next step: `/kronos-next`

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
