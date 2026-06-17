---
name: kronos-sanity-check
description: At the DOCS→COMMIT boundary, checks that PUBLIC changes in the code (new endpoints, models, pages, permissions) are reflected in the vault documentation updates. If something was forgotten — it flags it and DOCS returns to ⏳. Used when the user says /kronos-sanity-check, or automatically in kronos-next between DOCS and COMMIT.
---

# /kronos-sanity-check

A final check before COMMIT: "is everything PUBLIC documented?".

## Algorithm

### 1. Collect PUBLIC changes from the code git diff

```bash
cd <project>
git diff --staged    # the project's code
```

Extract **PUBLIC** markers from the diff:

- **New endpoints:** added lines `+@router\.(get|post|put|delete|patch)\(`
- **Changed endpoints:** context `@router\.` near +/- lines
- **New pages:** `+export function (\w+Page)\(` in `src/pages/`
- **New DB models:** `+class (\w+)\(Base\)` in models
- **New migrations:** new files in the migrations directory
- **New permissions / roles:** INSERT lines in migrations
- **config / branding:** configuration changes

If nothing PUBLIC is found → **PASS** (internal refactoring needs no docs).

### 2. Collect the vault diff

```bash
cd $VAULT_PATH
git diff
git status --porcelain
```

The list of modified/new files in the vault.

### 3. Reconciliation

For each PUBLIC change:
- Which document **should** reflect it (per the Routing Table)?
- Is that file in the vault's git status?

If **not** → flag "maybe forgotten: <change> → <expected file>".

### 4. Return the result

#### Success (all good):
```
✅ Sanity check passed
   PUBLIC changes: N
   All reflected in the vault diff (M files modified)

   You may proceed to COMMIT.
```

#### Flag (something was forgotten):
```
⚠️ Sanity check found issues:

  1. New endpoint: GET /api/v1/health/detailed
     Expected: docs/api-reference.md
     In vault diff: NOT found

  2. New permission: feature.new_module
     Expected: docs/permissions.md
     In vault diff: NOT found

The DOCS stage returns to ⏳ (rework required).
Recommendation:
  • Update the documents above
  • Run /kronos-sanity-check again
  • If skipped on purpose → /kronos-skip 4 <reason>
```

### 5. Apply the result

- **PASS** → writes "sanity check PASS" to the Activity log, DOCS stays [x]
- **FLAG** → writes "sanity check found N issues" to the Activity log, changes `[x] 4. **DOCS**` to `[⏳] 4. **DOCS**`, and adds each issue to the Decisions log

## What it does NOT do

- Does NOT update files itself (check only)
- Does NOT block the workflow directly (the hook does that)
- Does NOT check private changes (refactoring, optimization)
- Does NOT check documentation quality (only presence in the diff)

## Limitations

- Discovery: sometimes new code needs an entirely **new** document (one that does not exist yet). The sanity check will suggest creating it, but does not create it.
- If a change is PUBLIC but **not covered by the Routing Table** — it will be missed. This depends on the manually maintained table.
