---
name: kronos-route
description: Router/orchestrator for the KRONOS CODE stage. Invoked from /kronos-next when entering CODE for MEDIUM/LARGE tasks. Reads the plan, classifies subtasks by domain, maps each domain to a specialized subagent + model tier, decides count and parallel/pipeline, then (confirm-multi mode by default) either executes the dispatch plan or surfaces it for confirmation when it would spawn >=2 agents. ALWAYS logs the dispatch. Does not change the hook logic — it is a separate orchestration layer.
---

# /kronos-route

Turns the plan into a dispatch of **"domain -> specialist agent -> model -> parallel/pipeline"**.
Invoked from `/kronos-next` when entering CODE. It does NOT run the hook and does NOT close stages —
it only dispatches work; discipline and the commit-gate stay with the KRONOS hook, unchanged.

> **Important:** this skill is a playbook of rules. The actual agent spawning is done by the main
> loop (the `Workflow`/`Agent` tools), following this dispatch. The hook (`check-workflow.py`) does
> NOT call or execute the router.

## When the router does NOT run (returns "inline")
- **Type=TRIVIAL** -> 0 agents, the main loop makes the edits itself.
- The plan has no **"## Affected files"** section -> "inline" + a warning "add a file list to the plan".

## Algorithm

### 1. Context
- Read `WORKFLOW.md` -> `Type`, `Slug`.
- Read `plans/<slug>.md` -> the **"Affected files"** and **"Steps"** sections.
- Mode: env `KRONOS_ROUTE_MODE` (default `confirm-multi`).

### 2. Domain classification (by paths from "Affected files")
| Path / signal | Domain |
|---|---|
| backend API / services / background tasks, server-side source | **backend** |
| UI pages / components, client source, i18n/locale files | **frontend** |
| prompts / model-config / pipeline definitions | **pipeline** |
| migrations / schema changes | **migration** (critical) |
| docs / vault `*.md` | **docs** |
| single file <= 10 lines, NOT a critical path | **trivial-edit** |

### 3. Routing table (domain -> agent -> model tier)
| Domain | subagent (your project's specialist) | Model tier |
|---|---|---|
| backend | `backend-agent` | strong (flagship tier) |
| frontend | `frontend-agent` | strong (flagship tier) |
| pipeline | `pipeline-agent` | strong / mid |
| migration | `backend-agent` (+ always confirm) | strong |
| new module / architecture | `architect` | strong |
| trivial-edit / docs | `quick-editor` | mid |
| search / recon | `researcher` / `Explore` | light |

(Adapt the agent names to your own subagent registry. The model follows the chosen agent — the router
picks the agent, the model comes from that agent's definition.)

### 4. Count and execution mode
- **Size-gate:** TRIVIAL -> 0 · MEDIUM -> <=2 · LARGE -> <=5. More domains than the cap -> merge the small ones or sequence them.
- **Dependencies:** if frontend depends on a backend contract (a new endpoint the UI calls) -> **pipeline** (backend -> frontend). Independent domains -> **parallel**.
- **Shared files** (e.g. `i18n/*` locale files) must NOT be handed to two agents at once — one agent, or a final synthesis phase (avoid the write race).
- **Critical paths** (auth, permissions, migrations, security guards) -> mark `needsConfirm=true`.

### 5. Mode (`KRONOS_ROUTE_MODE`)
- **`confirm-multi`** (DEFAULT): `exec=auto` if agents **<=1** AND `needsConfirm=false`. If agents **>=2** OR a critical path is touched -> `exec=await` with COST-SAVING OPTIONS (see §6). Idea: cheap work (0-1 agent) runs without asking; an expensive fan-out is confirmed and can be downsized.
- **`auto-hybrid`**: `exec=auto` for clearly separated domains; `exec=await` only on a critical path (no agent-count trigger).
- **`always-confirm`**: `exec=await` always.
- **`always-auto`**: `exec=auto` always.

### 6. Record and output (ALWAYS)
- Append a line to `## Activity log` in WORKFLOW.md:
  `route: backend->backend-agent(strong) || frontend->frontend-agent(strong); mode=confirm-multi; exec=auto`
- Print the dispatch as a table.
- If `exec=await` -> show the dispatch to the user + **COST-SAVING OPTIONS** (via AskUserQuestion) and wait for a choice:
  1. **"Run as-is"** -> execute the full dispatch (§7).
  2. **"Just 1 agent"** -> collapse to one: pick the MAIN domain (priority backend > frontend > pipeline > other, or the one with the most subtasks), one agent does everything sequentially.
  3. **"I'll do it myself (0 agents)"** -> the main loop edits inline, no spawn.
  4. **"Cancel"** -> do not execute, return to the decision.
  (Append the choice to the log line: `exec=await->choice`.)
- If `exec=auto` -> the main loop executes immediately (see step 7).

### 7. Execution (done by the main loop)
- **parallel** -> the `Workflow` tool with `parallel(...)` OR several `Agent` calls (one per domain).
- **pipeline** -> the `Workflow` tool with `pipeline(...)`.
- Each agent gets: its `subagent_type` from the table + **its own file set** from "Affected files" + a hard
  instruction "edit ONLY your files; do not touch other domains or shared locale files".
- After spawning — normal CODE discipline: `git add` the files, `[x]` on a non-empty `git diff`.

## Guardrails
- Never spawn for **TRIVIAL**.
- Respect the per-Type cap (do not spawn agents for trivial work).
- Critical paths -> **always show the plan** (in any mode except `always-auto`).
- **>=2 agents** under the default `confirm-multi` -> show the plan + cost-saving options (can downsize to 1 agent / inline).
- **Always** log the dispatch (transparency — the user sees it after the fact).
- The router does NOT commit, does NOT close stages, does NOT change the hook.

## Fallback
- No "Affected files" -> inline + "complete the plan".
- Domain not recognized by path -> fall back to the extension, or `exec=await`.
