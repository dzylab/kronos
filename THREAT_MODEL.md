# KRONOS — Threat Model

KRONOS exists to stop work from being marked "done" before it actually is. Being explicit
about *who* it defends against keeps expectations honest: KRONOS is a **discipline / quality
gate**, not a **security boundary**.

---

## Assumption

KRONOS defends against an **honest-but-optimistic agent** (or human): one that genuinely
intends to do the work but declares a stage done prematurely — skips the plan, never runs the
tests, lets docs go stale, commits without a trace — usually out of optimism, haste, or a lost
thread of context.

It is **NOT** designed to stop a **hostile agent** that is actively trying to defeat the gate.
An adversary with shell access can trivially bypass it (see below); that is by design, not a
gap to be closed.

---

## Defends against

The `PreToolUse` hook re-verifies every `[x]` against the real artifact at `git commit` time,
so an optimistic agent cannot move past a stage it only *claimed* to finish:

- **Forged `[x]`** — the hook independently re-checks the fact and **blocks (exit 2)** on:
  - PLAN `[x]` without `plans/<slug>.md` (or under 50 lines)
  - CODE `[x]` with no real `git diff` in any tracked repo
  - TEST `[x]` with a `## Test log` shorter than 5 lines
  - DOCS `[x]` with no actual change in the docs vault
  - COMMIT `[x]` with no 7+ hex commit hash recorded
- **Skip without a reason** — a `⊘` stage is accepted only with a matching `SKIPPED stage N`
  entry in the Decisions log; otherwise it blocks.
- **Commit without plan / test / docs / hash** — the same gate, applied at commit time.
- **An unnoticed stall** (best-effort) — the watchdog flags a long stage whose objective probe
  has frozen, so a silently dead build/job does not masquerade as ongoing work.

---

## Does NOT defend against

- **A hostile agent with a shell.** `KRONOS_BYPASS=1` and editing `WORKFLOW.md` directly are
  **intentional** escape hatches. Anyone who can run shell commands can set the env var, rewrite
  the checkboxes, or remove the hook. KRONOS records bypasses in the Decisions log for
  accountability, but it does not — and cannot — prevent them.
- **Gaming the watchdog.** Progress signals can be faked (e.g. `touch` to bump mtime). The
  watchdog mitigates this with a forgeability gradient (process exit code > file content change
  > size/mtime > advisory HEARTBEAT) and an independent observer, but it remains a *heuristic
  early warning*, not proof of liveness. See `KRONOS.md` → Watchdog.
- **Semantics — KRONOS checks that work *happened*, not that it is *good*:**
  - TEST verifies that tests *ran and logged >= 5 lines*, **not** that they pass or are
    meaningful. Five lines of green-looking noise satisfy the gate.
  - PLAN verifies the plan is *>= 50 lines*, **not** that the plan is any good.
  - DOCS verifies the vault *changed*, **not** that the change documents the right thing.
  - A reviewer is still required for correctness and quality; KRONOS only guarantees the
    artifacts exist.
- **Parallel-edit conflicts.** The reserved-for-orchestrator contract (leaf files to fan-out
  agents, convergence points edited serially — see `KRONOS.md` → Smart Parallelism) is a
  **convention, not enforcement**. The hook does not detect two agents clobbering the same file;
  use `isolation: "worktree"` for genuinely shared zones.
- **Commits to the documentation vault (intentional carve-out).** A commit whose target repo is
  the `VAULT_PATH` vault is **not gated** — it is the DOCS-stage product, not code. The blast
  radius is bounded: the exemption fires **only** when the commit's git-toplevel exactly equals
  the vault's git-toplevel; every code repo (project root / submodules) is unaffected and stays
  gated. The self-test pins this with a positive case (vault commit passes under a blocking
  workflow) **and** a control (a project commit under the same workflow still blocks), so the
  exemption cannot silently widen to code. It does not let an agent slip *code* past the gate —
  only *documentation* into the vault repo, which is what DOCS already expects.

---

## In one line

KRONOS raises the floor for an honest agent and leaves an auditable trail; it does not raise the
ceiling against a hostile one, and it never judges whether the work is *correct* — only that it
*occurred*.
