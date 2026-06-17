# Project Standards — web project (EXAMPLE / optional)

This is an **example** of the *project-specific* standards YOU would write for a web app — it is
**not** part of the KRONOS core. KRONOS's own canons (`STANDARDS.example.md`) stay universal and
stack-agnostic; this file shows how a team layers its own stack conventions on top. **Copy what fits,
delete the rest, adapt to your stack.** Frameworks churn (Redux -> Zustand -> signals; pages ->
app router) — treat every rule here as a starting opinion, not law.

Use it like `STANDARDS.example.md`: copy to `STANDARDS.md` and `/kronos-code-standards` loads it before
the CODE stage. Override order: env `KRONOS_STANDARDS_PATH` -> `<project>/STANDARDS.md` ->
`~/.claude/STANDARDS.md` -> built-in defaults.

---

## Components
- One component = one responsibility. If it both fetches data and renders a complex tree, split the
  fetch (a hook or a container) from the presentation.
- Props are explicit and typed. No "god prop" object a child reaches into — pass only what is used.
- Document a shared/reusable component with a short prop table (name · type · required · purpose) and
  one usage example. A component nobody can use without reading its source is undocumented.
- Co-locate: a component's styles, tests, and stories live next to it, not in distant folders.
- Extract a component when it is reused **or** when a parent grows past one screen — not speculatively.

## Routing
- Pick ONE routing model and keep it: file-based (an `app/` or `pages/` tree) **or** a central route
  config — never both for the same area.
- Route definitions live in one predictable place; a new contributor finds "where do URLs map to
  views" in under a minute.
- Keep data-loading at the route boundary (loader / server component / route-level fetch), not buried
  three components deep — a route's data dependencies should be visible at the route.
- URLs are the source of truth for shareable state (filters, tabs, pagination), not local state that
  resets on refresh.

## State management
- **Local first.** Component state by default; lift only when two siblings genuinely need to share.
- Reach for a global store only when state is truly app-wide (auth/session, theme, cart). Most state
  is *server* state — use a data-fetching cache (a query library) for it, not a hand-rolled store.
- One store boundary, clearly named. Don't scatter one domain across a global store, context, and
  local state — pick the owner.
- Server state != client state. Don't copy fetched data into a global store "to be safe" — that is the
  duplicate-source-of-truth smell.

---

> These are illustrative opinions for a JS/TS web app, written to be adapted. KRONOS verifies *facts*
> (a plan exists, tests ran, docs changed) — it does **not** enforce these patterns. They are guidance
> the `/kronos-code-standards` skill hands your code agents, nothing more.
