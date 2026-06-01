<img width="1672" height="941" alt="KRONOS" src="https://github.com/user-attachments/assets/3246641b-3815-491a-af79-c8fd602da5a3" />

# KRONOS Workflow Engine

> A workflow orchestration and verification engine for AI-assisted software development —
> planner, orchestrator, documentation routing, watchdog, and a verification hook.
> Every task runs through **PLAN → CODE → TEST → DOCS → COMMIT**, and the hook verifies the
> *facts*, not the checkboxes.

> **Every task starts with a plan. Every plan must be executed. Every completed stage must be verified.**

KRONOS is a lightweight workflow engine built on top of [Claude Code](https://claude.com/claude-code)
hooks and slash-commands. It exists to solve one problem: **AI agents (and humans) mark
work "done" before it actually is.** A plan gets skipped, tests never run, docs go stale,
and a green checkmark hides a broken commit.

KRONOS makes that impossible. When you try to `git commit`, a `PreToolUse` hook reads
`WORKFLOW.md` and, for every stage marked `[x]`, **re-checks the real artifact**:

| Stage | Marked `[x]` is accepted only if… |
|-------|-----------------------------------|
| **PLAN** | `plans/<slug>.md` exists **and** is ≥ 50 lines |
| **CODE** | `git diff` is non-empty in at least one tracked repo |
| **TEST** | the `## Test log` section has ≥ 5 lines of real output |
| **DOCS** | `## Docs updated` lists files **and** the docs vault shows git changes |
| **COMMIT** | a 7+ char commit hash is recorded in the Activity log |

Lie about any of them and the hook returns `exit 2` — the commit is blocked with a
clear message. You can't fake your way past it.

---

## Philosophy

KRONOS was built to solve a practical problem: keeping code, documentation, and project
knowledge synchronized while working with AI agents. The core idea is simple:

> **Do not trust an AI agent when it says a task is complete. Verify artifacts instead.**

After working with AI coding tools, the same problems appeared repeatedly: documentation
went stale, project knowledge was lost over time, agents reported tasks as complete while
important work was still missing, context had to be rebuilt again and again (wasting time
and tokens), and architectural decisions disappeared into chat history.

The primary goal is **not** autonomous AI. The goal is a **structured, predictable, and
verifiable** development workflow. Completion is not determined by what an agent says — it
is determined by what can be verified.

Core principles:

- **Planning first.** Every task is analyzed and broken into stages with explicit completion
  criteria before implementation begins. Execution follows the plan; verification confirms it.
- **Documentation is part of development.** If the system changes, documentation changes —
  it is a required stage, not an optional task for later.
- **Specialized responsibilities.** Each component has one role: the **planner** creates
  plans, the **orchestrator** drives execution, **agents** perform tasks, the **hook**
  validates results, and documentation stays synchronized with reality.
- **Verification over trust.** Completion is evidence — plans, code changes, test runs, doc
  updates, workflow state, commit history — never a declaration.
- **Knowledge retention.** Code can be restored from Git; project knowledge cannot. KRONOS
  preserves architecture decisions and operational context through continuous doc updates.
- **Structured parallelism.** Speed without losing control — agents work within clearly
  defined boundaries while orchestration stays centralized.

---

## Why

LLM agents are optimistic. They write `- [x] TEST` and move on, even when nothing ran.
Code review catches some of it; a lot slips through. KRONOS turns the discipline into
an enforced gate instead of a hopeful convention. The result: every commit on a KRONOS
project has a plan behind it, a test log, updated docs, and a traceable hash.

It also adds:

- **Auto-classification** of each task into `TRIVIAL` / `MEDIUM` / `LARGE`, which decides
  how many stages run and how much work is parallelized across sub-agents.
- **Documentation routing** — a 3-layer system (static table → grep discovery → sanity
  check) that figures out *which* docs a code change should update, so docs don't rot.
- **A bypass hatch** (`KRONOS_BYPASS=1`) for genuine hotfixes — every bypass is recorded
  in the Decisions log, so accountability is preserved.
- **A watchdog** (`/kronos-watchdog`) — a *cross-cutting* stuck-task detector (not a 6th
  stage) that runs during long stages. It judges by *progress* (a growing output file, a
  live process, a responsive endpoint), not a dumb timeout, so it never kills an honest
  slow build — only flags one that has truly frozen, and suggests retry / skip.
- **An explicit threat model** ([THREAT_MODEL.md](THREAT_MODEL.md)) — KRONOS is a
  discipline/quality gate against an *honest-but-optimistic* agent, **not** a security
  boundary against a hostile one. The doc spells out exactly what it does and does not
  defend against (it checks that work *happened*, not that it is *correct*).

---

## The 5 stages

```
PLAN ──▶ CODE ──▶ TEST ──▶ DOCS ──▶ COMMIT
 │        │        │        │         │
 plan    git      test     docs      commit
 ≥50ln   diff     log≥5    vault     hash
                           changed
```

Each stage is a checkbox in `WORKFLOW.md`. The slash-command `/kronos-next` advances to
the next open stage, does the work, and marks it `[x]` **only after verifying the fact**.
The hook independently re-verifies at commit time.

`⊘` means a stage was deliberately **skipped** via `/kronos-skip <N> <reason>` — the hook
accepts it, but requires a matching `SKIPPED stage N` line in the Decisions log.

---

## Task categories (auto-classified)

| Type | Trigger | Stages | Parallel sub-agents |
|------|---------|--------|---------------------|
| **TRIVIAL** | 1 file, ≤10 lines, not a critical path | 3 (PLAN + TEST skipped) | 0 |
| **MEDIUM** | 1 module, 2–3 files (default) | 5 | 2 |
| **LARGE** | 3+ modules / migration + UI | 5 | up to 5 |

---

## Slash commands

| Command | What it does |
|---------|--------------|
| `/kronos-start <name>` | Start a workflow: Plan-agent writes `plans/<slug>.md`, auto-classifies Type, fills `WORKFLOW.md`. |
| `/kronos-next` | Advance to the next open stage with Type-based parallelism. |
| `/kronos-route` | Orchestration layer for CODE: maps plan domains → specialist subagents + model tiers, decides parallel/pipeline, auto-dispatches (or asks on critical paths). Invoked by `/kronos-next`. |
| `/kronos-status` | Read-only status of the current workflow (✅ ⏳ ⊘ ⬜). |
| `/kronos-skip <N> <reason>` | Mark a stage `⊘` skipped + log the reason. |
| `/kronos-find-docs` | Routing table + grep discovery → list of docs to update. |
| `/kronos-sanity-check` | Before COMMIT: are all public changes (endpoints, models, pages) documented? |
| `/kronos-watchdog` | Cross-cutting stuck-task detector: probes progress of an active long-running stage (see below). |

---

## Install

```bash
git clone <this-repo> kronos
cd kronos

# 1. configure
cp config.example.yaml config.yaml
$EDITOR config.yaml          # set PROJECT_PATH and VAULT_PATH

# 2. install hooks + skills into ~/.claude
./install.sh

# 3. register the hook in ~/.claude/settings.json (install.sh prints the snippet)

# 4. verify it works
python ~/.claude/hooks/check-workflow.py --self-test
```

The self-test spins up throwaway git repos and runs ~24 cases (blocked commits, bypass,
fake checkboxes, skipped-with-reason, watchdog heartbeat hard-gate — a `[x]` stage without a
`STARTED` trace blocks the commit, PLAN-stage exemption, legacy/template-state pass,
real-task-with-angle-brackets, etc.). All should pass.

### settings.json hook registration

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|PowerShell",
        "hooks": [
          { "type": "command", "command": "bash ~/.claude/hooks/check-workflow.sh" }
        ]
      }
    ]
  }
}
```

The hook only acts on `git commit` / `git push`. Read-only git (`status`, `log`, `diff`)
and every other command pass straight through.

---

## Configuration

All via environment variables (see `config.example.yaml`). Paths support `~` and `$VAR`.

| Variable | Purpose | Default |
|----------|---------|---------|
| `PROJECT_PATH` | Root of the main project (repo with `WORKFLOW.md`) | hook's cwd |
| `VAULT_PATH` | Separate git repo for docs / notes / wiki | sibling `vault`/`docs`/`wiki` |
| `KRONOS_REPOS` | Extra repos to check for diff (submodules), comma-separated | empty |
| `KRONOS_BYPASS` | `1` to bypass the gate (recorded in Decisions log) | unset |

---

## Documentation routing

When the DOCS stage runs, KRONOS figures out which docs need updating using three layers,
in order:

1. **Routing table** (`KRONOS-ROUTING.md`, from the `.example`) — a static map of
   `code file → doc file`. Instant, covers ~80%. You maintain it as you add modules.
2. **Discovery agent** (`/kronos-find-docs`) — extracts keys (endpoints, function/class
   names) from the git diff and greps the vault for them. Catches what the table misses.
3. **Sanity check** (`/kronos-sanity-check`) — right before COMMIT, compares the *public*
   surface changed in code (new endpoints, models, pages, permissions) against what
   actually changed in the vault. Flags anything undocumented and reopens DOCS.

---

## Repository layout it expects

KRONOS works with 1–N local git repos:

- **Main project** — where `WORKFLOW.md` lives (your code).
- **Docs vault** (optional) — a *separate* repo for documentation (`VAULT_PATH`).
- **Extra repos** (optional) — submodules / sibling modules (`KRONOS_REPOS`).

CODE is considered done if **any** of them has a diff. All git stays local; deploy to
servers via scp/rsync/CI, never `git commit` on prod.

---

## Files in this repo

```
kronos/
├── README.md                     # this file
├── LICENSE                       # GPL-3.0
├── KRONOS.md                     # full engine documentation
├── THREAT_MODEL.md               # what it does / doesn't defend against
├── KRONOS-ROUTING.example.md     # template for your code→docs map
├── WORKFLOW.template.md          # the 5-stage workflow template
├── config.example.yaml           # configuration template
├── install.sh                    # installer → ~/.claude/
├── hooks/
│   ├── check-workflow.py         # the verification logic (+ --self-test)
│   └── check-workflow.sh         # bash wrapper (Windows/MSYS-safe)
└── skills/
    ├── kronos-start/SKILL.md
    ├── kronos-next/SKILL.md
    ├── kronos-route/SKILL.md
    ├── kronos-status/SKILL.md
    ├── kronos-skip/SKILL.md
    ├── kronos-find-docs/SKILL.md
    ├── kronos-sanity-check/SKILL.md
    └── kronos-watchdog/SKILL.md
```

---

## What KRONOS is not

- Not an autonomous AI framework, and not a fully autonomous coding agent.
- Not a replacement for software-engineering practices or code review.
- Not a project-management platform.
- Not a commercial product.

It is a workflow layer focused on planning, execution, verification, and documentation.

---

## Notes

- The hook is **cross-shell** — the matcher covers both Bash and PowerShell, and the
  Python core handles UTF-8 paths and resolves the interpreter on Windows/MSYS.
- See [THREAT_MODEL.md](THREAT_MODEL.md) for exactly what KRONOS does and does not defend
  against — it is a discipline gate, not a security boundary.

## Open source & support

This project is shared because it may be useful to others. There is no commercial roadmap,
no guarantees, and no expectation of support. If it improves your workflow, use it; if you
find a better solution, improve it. Issues, pull requests, and suggestions are welcome, but
responses are not guaranteed. Provided as-is — use at your own risk.

## Author

Created and maintained by **dzylab** — [@dzylab](https://github.com/dzylab) · <https://github.com/dzylab>

## License

KRONOS is licensed under the **GNU General Public License v3.0 (GPL-3.0)** — see
[LICENSE](LICENSE) for the full text.

You may use, modify, and distribute this software. **If you distribute modified versions,
you must also make the source available under the same GPL-3.0 license.** The goal is
collaboration and shared improvement, not closed-source repackaging.

```
Copyright (C) 2026 dzylab (https://github.com/dzylab)

This program is free software: you can redistribute it and/or modify it under the terms
of the GNU General Public License as published by the Free Software Foundation, either
version 3 of the License, or (at your option) any later version. This program is
distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY. See the GNU
General Public License for more details.
```

---

## Final note

The most important feature of KRONOS is not orchestration. It is ensuring that work follows
a plan, that completion can be **independently verified**, and that project knowledge stays
synchronized with reality. Everything else exists to support those goals.
