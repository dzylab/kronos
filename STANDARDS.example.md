# Project Standards — code & documentation canons (example)

Read by `/kronos-code-standards` (before CODE) and `/kronos-doc-standards` (before DOCS).
This file holds **universal canons only**. Project-specific rules (your i18n policy, "always give
code in full", date helpers, transaction patterns, your docs layout) live in your own project
instructions (e.g. `AGENTS.md` / `CLAUDE.md`) — the skill tells the agent to apply **both** these
canons **and** the project rules.

Copy this file to `STANDARDS.md` and edit. Override order: env `KRONOS_STANDARDS_PATH` →
`<project>/STANDARDS.md` → `~/.claude/STANDARDS.md` → built-in defaults baked into the skill.

---

## Code Standards

**Canon: Clean Code (R. C. Martin).**
- A function does ONE thing and does it well. If you cannot summarize it in one sentence, it is too big.
- Size guide: a function should be <= ~20 lines (a guide, not a hard gate). Nesting depth <= 3.
- Names are descriptive and precise: `calculate_total()`, not `calc()`; `is_paid`, not `flag`.
- DRY: anything repeated more than twice becomes a function/module.
- A comment explains **why** (the decision/tradeoff), not **what** (the what should read from the code).
- No dead code, no commented-out blocks, no debug prints in a commit. Fail fast.
- Errors are explicit: never swallow exceptions silently (use a savepoint for SQL side-effects).

**Style guides by language** (follow what the project adopts; defaults):
- Python -> PEP 8. Linter: `ruff`; types: `mypy`. Formatter: `ruff format` / `black`.
- JS/TS -> Google or project style. Linter: `eslint`. Formatter: `prettier`.
- Other -> the language community standard + consistency with the existing code.

**Consistency beats personal preference.** One style per project; never mix conventions.

**Linters (optional enforcement):** if the project configures a linter, the skill may run it and report
green/red (advisory). Command via `KRONOS_LINT_CMD` (env) or the line below. Empty -> the check is skipped.
- LINT_CMD: <unset — fill in for your project, e.g. `ruff check . && eslint .`>

**Design principles (apply with judgment — simplicity first).**
- KISS / YAGNI rule the rest: write the plainest code that solves the problem NOW. A principle or
  pattern earns its place only when it removes pain that already exists — never speculatively, never
  to look clever.
- SOLID quick-checks: one reason to change (S); extend by adding code, not editing tested code (O);
  a subtype works anywhere its base does (L); many small interfaces over one fat one (I); depend on
  abstractions, not concretes (D).
- DRY (but copy twice before you abstract — rule of three); composition over inheritance; Law of
  Demeter (`a.b().c().d()` is a smell); fail fast at the boundary.
- Smells with mechanical thresholds (a linter can gate these): long method > 50 lines, long parameter
  list > 4, large file/class > 500 lines, deep nesting > 4, cyclomatic complexity > 10, duplicate
  blocks, dead/commented-out code, magic literals.
- Reach for a pattern ONLY when its smell is already there: switch-on-type -> Strategy/State; many
  optional args -> Builder; scattered object creation -> Factory; notify many -> Observer; wrap a
  third-party API -> Adapter/Facade; behavior without a subclass explosion -> Decorator.
- This is guidance, not a gate. The hook verifies facts; "good design" is not machine-verifiable. Only
  the mechanical thresholds above are enforceable, and only via a linter.

---

## Doc Standards

**Canon: Diataxis** — four documentation types, each for its OWN need, never mixed:
| Type | Answers | Form |
|---|---|---|
| **Tutorial** | "teach me from zero" | a hands-on lesson, guaranteed to succeed |
| **How-to** | "how do I solve task X" | a recipe of steps for someone who already knows |
| **Reference** | "what are the facts / the API" | dry, accurate description, no interpretation, complete |
| **Explanation** | "why is it built this way" | context, reasons, tradeoffs, discussion |

**Density (no filler):**
- A dry, cold extract. No marketing, no padding, nothing self-evident.
- One idea per paragraph. A table/list beats prose where possible.
- Be concrete: file paths, names, numbers, commands. Not "configure accordingly".
- Do not duplicate what another doc already states — link to it (unless a doc must be self-contained).

**Frontmatter (required, project schema):** `type`, `status`, `tags`, `date`.

**Link hygiene:** internal links resolve; paths are relative to the docs root. For self-contained
sections, respect their self-containment rule (keep external info inline rather than linking out).

**Structure by type (expected skeleton):**
- Reference: title -> one-line purpose -> a table/list of facts (fields, endpoints, parameters).
- How-to: task -> prerequisites -> numbered steps -> a check that the result works.
- Explanation: thesis -> context -> reasons/alternatives -> consequences.
- Tutorial: goal -> steps each with expected output -> a "what you built" wrap-up.
