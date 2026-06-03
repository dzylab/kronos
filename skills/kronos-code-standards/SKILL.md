---
name: kronos-code-standards
description: Loads code canons (Clean Code + style guides + project rules) BEFORE the CODE stage and produces a STANDARDS block that the dispatched code agents (/kronos-route) receive in their instructions — so they write short blocks to standard, no filler, like a 20-year veteran. Invoked from /kronos-next on entering CODE (Type != TRIVIAL), or manually: /kronos-code-standards, "load code standards", "how to write code to canon". Guidance only — blocks NOTHING.
---

# /kronos-code-standards

A code-quality layer before CODE. It does NOT close the stage, does NOT block the commit, does NOT
change the hook — it is guidance the main loop attaches to each code agent in `/kronos-route §7`. Same
model as the router: a playbook the hook never calls.

🔴 **Honest boundary:** "write like a veteran / no filler" is **guidance** (it shapes the LLM output,
it is not machine-verifiable). A real green/red only comes from a linter, if one is configured (advisory).

## Algorithm

### 1. Type gate
Read `WORKFLOW.md` -> `Type`. If `TRIVIAL` -> log `code-standards: skipped (TRIVIAL)` and exit.

### 2. Load standards (override chain)
`KRONOS_STANDARDS_PATH` (env) -> `<project>/STANDARDS.md` -> `~/.claude/STANDARDS.md` -> **built-in
defaults** (below). Parse the `## Code Standards` section. No file -> built-in defaults + log
`code-standards: using built-in defaults (no STANDARDS.md found)` (do NOT fail — backward-compat).

**Built-in defaults (if no STANDARDS.md):** a function = single responsibility, <=~20 lines, nesting
<=3; descriptive names; DRY; comments explain "why"; no dead code/debug prints; fail fast; style by
language (Python -> PEP 8 / ruff / mypy, JS/TS -> eslint / prettier); consistency beats taste.

### 3. Detect languages
From the plan `plans/<slug>.md` "Affected files" section + `git diff --name-only` (staged+unstaged).
Map extensions -> language -> style guide + linter (`.py` -> PEP 8 / ruff, `.ts/.tsx` -> eslint / prettier).

### 4. Build the STANDARDS block
A short copy-paste block for each code agent:
```
[CODE STANDARDS — apply everything below]
Canon: Clean Code — single responsibility, <=~20 lines, descriptive names, DRY, comments say "why".
Languages: <e.g. py -> PEP 8 / ruff, tsx -> eslint / prettier>. Stay consistent with existing code.
Project rules (your project instructions): apply them TOO (i18n policy, "give code in full", date
  helpers, transaction/savepoint patterns, etc.).
Forbidden: dead code, debug prints, commented-out blocks, silently swallowing errors.
```
The main loop appends this block to each agent's instructions in `/kronos-route §7`.

### 5. Log (ALWAYS)
In `## Activity log`: `code-standards: canon=CleanCode; langs=<py,tsx>; lint=<cmd|none>`.

### 6. Optional linter (advisory)
If `KRONOS_LINT_CMD` (env) or a `LINT_CMD` line in STANDARDS.md is set and the linter is installed — run
it, show green/red + log `lint: PASSED|FAILED (<cmd>)`. **Red = advice only, NOT a block** in this
version. No linter -> `lint: none configured (advisory only)`. Teeth (routing lint output into the Test
log under `KRONOS_LINT_GATE=1`) are a future flag, not active now.

### 7. Always PASS
The skill always "passes" (it is guidance). The CODE stage is closed by `/kronos-next` on a non-empty
`git diff`, not by this skill.

## What it does NOT do
- Does not edit code (read-only — it only steers the agents).
- Does not close/block stages. Does not change `check-workflow.py`.
- Does not run backups.
