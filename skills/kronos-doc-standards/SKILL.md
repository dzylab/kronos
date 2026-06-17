---
name: kronos-doc-standards
description: Loads doc canons (Diataxis + density + frontmatter) BEFORE the DOCS stage, classifies the target docs by type, and produces a DOC-STANDARDS block that the parallel doc agents receive in their instructions — so docs are a structured, dense extract, no filler, no junk. Invoked from /kronos-next as the first DOCS step (Type != TRIVIAL), or manually: /kronos-doc-standards, "load doc standards", "how to write docs to canon". Guidance only — blocks NOTHING.
---

# /kronos-doc-standards

A doc-quality layer before DOCS. It does NOT close the stage, does NOT block the commit, does NOT change
the hook. It is orthogonal to `/kronos-find-docs` (which finds WHICH files) and `/kronos-sanity-check`
(which checks COVERAGE). This skill sets QUALITY+STRUCTURE: it classifies by Diataxis and produces a
block for the doc agents.

🔴 **Honest boundary:** frontmatter / required headings / broken links are checkable (but advisory).
"Density / no filler" is NOT machine-checkable — at best an optional LLM judge, never a gate.

## Algorithm

### 1. Type gate
`WORKFLOW.md` -> `Type`. If `TRIVIAL` -> log `doc-standards: skipped (TRIVIAL)` and exit.

### 2. Load standards
`KRONOS_STANDARDS_PATH` -> `<project>/STANDARDS.md` -> `~/.claude/STANDARDS.md` -> **built-in defaults**.
Parse `## Doc Standards`. No file -> built-in Diataxis + log `doc-standards: using built-in defaults`
(do not fail).

**Built-in defaults:** Diataxis (tutorial/how-to/reference/explanation); density (a dry extract, one
idea per paragraph, table > prose, be concrete); frontmatter `type/status/tags/date`; links resolve.

### 3. Classify each target doc by Diataxis
Files: from `/kronos-find-docs` (if already run) or `git -C <vault> status --porcelain`. Type by
path+name+content:
- `*Reference*`, `*API*`, `*Schema*`, fact tables -> **reference**
- `*Troubleshooting*`, `*How-to*`, `*Common-Tasks*`, recipes -> **how-to**
- `*Architecture*`, `*Overview*`, "why", rationale -> **explanation**
- `*Getting-Started*`, `*Local-Development*`, learn-from-zero -> **tutorial**
Print a table: `file -> type -> expected skeleton`.

### 4. Build the DOC-STANDARDS block
For each doc agent:
```
[DOC STANDARDS — apply everything below]
Type (Diataxis): <reference|how-to|explanation|tutorial> — do NOT mix types in one doc.
Skeleton: <by type: reference=purpose+fact table; how-to=task+steps+check; ...>
Density: a dry extract, no filler/marketing/self-evident text; one idea per paragraph; table > prose;
  be concrete (paths, names, numbers, commands).
Frontmatter required: type/status/tags/date. Links resolve; paths relative to the docs root.
Project rules (your project instructions): apply them TOO (e.g. a section's self-containment rule,
  a "general vs CONFIG-TO-REPLACE" whitelabel split).
```

### 5. Log (ALWAYS)
`## Activity log`: `doc-standards: canon=Diataxis; files=N; types=ref x2, howto x1`.

### 6. Optional machine checks (advisory)
- frontmatter: are `type/status/tags/date` present;
- required headings per type;
- broken internal/relative links (resolve under the vault).
All **advisory** (show + recommend, do not block). "Density" -> optional LLM self-review under
`KRONOS_DOC_LLM_REVIEW=1` (a cheap model flags filler) — a judge, not a gate.

### 7. Always PASS
The real DOCS gate stays `verify_docs` (vault modified + "Docs updated" non-empty) + `/kronos-sanity-
check`. This skill does not replace them.

## What it does NOT do
- Does not edit docs (read-only — it only steers the agents).
- Does not close/block stages. Does not change `check-workflow.py`. Does not run backups.
