---
name: kronos-verify
description: Run the project's test oracle + pytest, summarize the result, and fill the WORKFLOW.md '## Test log' with a ready green/red artifact for the TEST stage. Used when the user says /kronos-verify, or automatically on the TEST stage before marking it [x]. Produces the success/failure markers the correctness TEST-gate checks.
---

# /kronos-verify

Runs your test commands, prints a summary, and writes a ready artifact into the `## Test log`
of WORKFLOW.md — so the correctness TEST-gate (in the hook) sees a REAL green/red run.

## Algorithm

1. Discover the test command(s) for this project. Defaults, in order:
   - a project **oracle** if present (e.g. an import/route check that prints `ALL CHECKS PASSED`)
   - `pytest -q` (prints `N passed` / `N failed`)
   - configurable: a `KRONOS_VERIFY_CMD` env var, or a `verify:` line in config.yaml
2. Run each command, capture stdout/stderr. For a long run, arm a **Monitor** and use
   `/kronos-watchdog` — do not treat a long run as dead until it says 🔴STALLED.
3. Parse the result:
   - success markers: `N passed`, `PASSED`, `ALL CHECKS PASSED`, `OK`
   - failure markers: `N failed` (N>0), `FAILED`, `Traceback`
4. Write the captured output into the `## Test log` section of WORKFLOW.md (>= 5 real lines,
   including the pass/fail summary). This is exactly what the hook's correctness gate reads.
5. Report: 🟢 green (safe to mark `TEST [x]`) or 🔴 red (fix first; TEST stays `[ ]`).

## Why
The correctness TEST-gate blocks `TEST[x]` unless the Test log shows a real green run (a
success marker, no failure marker). `/kronos-verify` produces that artifact honestly — you
cannot mark TEST done on a red or empty run.

## What it does NOT do
- Does not mark `TEST [x]` itself (that's `/kronos-next` after a green run).
- Does not fix failing tests.
- Does not run destructive operations.
