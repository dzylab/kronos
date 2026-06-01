---
name: kronos-find-docs
description: On the DOCS stage, determines the list of documentation files to update for the code changes. Uses 2 mechanisms in sequence: Routing Table lookup (instant) + Discovery Agent via Grep over the vault (10-15 s). Used when the user says /kronos-find-docs, or automatically on the DOCS stage of a workflow.
---

# /kronos-find-docs

Determines which documents in the vault (`VAULT_PATH`) to update for the current code changes.

## Algorithm

### 1. Collect the list of changed files

```bash
cd <project>
git diff --name-only HEAD          # unstaged
git diff --cached --name-only      # staged
# Merge, drop duplicates
```

### 2. Routing Table lookup (instant)

Read `KRONOS-ROUTING.md` (your local map based on `KRONOS-ROUTING.example.md`). For each changed file:
- Find an exact match in the left column (including wildcards like `src/pages/admin/*Page.tsx`)
- If matched → add the right column to the "routing-found" list

Covers ~80% of cases. Time: <1 s.

### 3. Discovery Agent (Grep over the vault)

Extract keys from the git diff for the remaining files:
- **Endpoints:** `@router\.(get|post|put|delete|patch)\(['"]([^'"]+)['"]` — endpoint paths
- **Functions:** `^(?:async )?def (\w+)\(` — function names
- **Classes:** `^class (\w+)[:\(]` — class names
- **Pages/components:** `export function (\w+Page)\(` — page components
- **Localization keys:** changed keys in i18n files

Run a `Grep` agent over `VAULT_PATH` for these keys. Use an `Explore` subagent if there are many keys (>5) — it is faster.

Time: 10-15 s.

### 4. Merge + dedupe

- Routing set + Discovery set
- Drop duplicates (`set`)
- Sort (stable order)

### 5. Verify existence

For each candidate file:
- Check `ls $VAULT_PATH/<path>` — does it exist?
- If not → do not include it in the final list (or suggest creating it with a "*maybe worth creating*" flag)

### 6. Return the list

Output format:

```
🔍 Found N files to update:

Routing Table (M files):
  • docs/api-reference.md
  • docs/features/client-cabinet.md

Discovery Agent (K files):
  • docs/troubleshooting.md (matched on key: AuthGuard)
  • sessions/2026-01-15-fix.md (on key: pickItems)

Maybe worth creating (Q files):
  • docs/new-feature.md (new module X is not documented)

Next step: launch parallel agents on each file in the list to update it.
Then /kronos-sanity-check before COMMIT.
```

## If something breaks

- `git diff --name-only` is empty → no staged/unstaged changes → do nothing, ask the user
- `KRONOS-ROUTING.md` not found → fall back to Discovery only
- Grep timeout → return what was found within the timeout + warn

## What it does NOT do

- Does NOT update files itself (that's the main agent's job after the list is returned)
- Does NOT run the sanity check (that's a separate `/kronos-sanity-check`)
- Does NOT block the workflow
