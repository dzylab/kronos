# Active Workflow

**Task:** <task name>
**Started:**
**Slug:** <slug>
**Type:** <!-- TRIVIAL / MICRO / MEDIUM / LARGE / OPS -->
<!-- MICRO = lightweight increment (PLAN 1 line + TEST + COMMIT; verify_plan drops the 50-line floor).
     OPS = multi-commit pipeline: instead of the 5 stages, a "## OPS Checklist" of sub-steps
     (test→drift→stage→merge→deploy→smoke), each closed by its own commit;
     an [x] sub-step without a trace (hash/PASSED/done) → BLOCK. -->

## Stages (5 stages)

- [ ] 1. **PLAN** → `plans/<slug>.md` >= 50 lines + user sign-off
- [ ] 2. **CODE** → `git diff` is non-empty, no TS/lint errors
- [ ] 3. **TEST** → the '## Test log' section below has >= 5 lines of real output
- [ ] 4. **DOCS** → the '## Docs updated' section + `git status VAULT_PATH` confirms
- [ ] 5. **COMMIT** → commit hash in the Activity log + push (or 'no remote' in Decisions)

## Heartbeat

<!-- Fill in when a LONG stage starts (build, background Bash job, external agent/server).
     The watchdog (/kronos-watchdog) guards progress — a cross-cutting check, NOT a 6th stage.
     SLA_SOFT defaults by Type (min): TRIVIAL 5 / MEDIUM 15 / LARGE 30. SLA_HARD = 2 x SLA_SOFT.
     If there is no active long stage, leave STAGE: - (nothing to guard).

     STALLED is judged from the watchdog's own PROBE observations logged in the Activity
     log (objective signal), NOT from HEARTBEAT below. HEARTBEAT is an advisory marker the
     agent writes; it is never the source of truth for STALLED. -->

- STAGE:     -                            <!-- active long stage (PLAN/CODE/TEST/DOCS) or - -->
- STARTED:                                <!-- timestamp the stage started -->
- HEARTBEAT:                              <!-- (advisory) timestamp of the last progress the agent noted -->
- SLA_SOFT:                               <!-- soft threshold, min → probe/observe -->
- SLA_HARD:                               <!-- hard threshold, min → STALLED -->
- PROBE:                                  <!-- how to measure progress: output file grows / process R|S / endpoint 200 -->

## Test log

<!-- real output of tests/checks, >= 5 lines -->

## Docs updated

<!-- list of documentation files you updated (one per line, relative to the vault root) -->

## Activity log

<!-- timestamp + what was done, reverse chronological order.
     Watchdog verdicts go here too: ALIVE / SLOW / STALLED + the observed probe value. -->

## Decisions log

<!-- decisions, escape hatches (KRONOS_BYPASS), skipped stages (⊘ + reason), deviations from the plan -->
