# KRONOS Routing Table — code → documentation (TEMPLATE)

**Purpose:** a static map of "when file X in the code changes → update document Y in `VAULT_PATH`".

**Used by:** the `/kronos-find-docs` skill on the DOCS stage of a workflow.

**Maintenance rule:** when you add a new module (a new API/page file) — **in the same CODE stage** add a line to this table. Otherwise the routing goes stale.

> 📋 This is an **example**. Copy it to `KRONOS-ROUTING.md` and replace `<YOUR_MODULE>` / `<YOUR_VAULT_FOLDER>` for your project.

---

## Where to commit (repositories)

| File type | Git repo for `git commit` |
|---|---|
| `<PROJECT>/src/**`, application code | **the main project repo** (`PROJECT_PATH`) |
| `<SUBMODULE>/**` (if a submodule exists) | **the submodule** (its own history). Then bump the submodule in the parent. |
| `<VAULT>/**/*.md` (documentation) | **the vault repo** (`VAULT_PATH`, a separate git repo) |
| `WORKFLOW.md` | **never** (in `.gitignore`) |
| `~/.claude/**` (KRONOS config) | **never** (the user's global folder) |

All git operations are **local**. Files reach prod via scp/rsync/CI, bypassing git on the server.

---

## Backend code → documentation

| Change in | Update |
|---|---|
| `<PROJECT>/api/auth.<ext>` | `<YOUR_VAULT_FOLDER>/permissions.md` |
| `<PROJECT>/api/<YOUR_MODULE>.<ext>` | `<YOUR_VAULT_FOLDER>/api-reference.md` + `<YOUR_VAULT_FOLDER>/features/<YOUR_MODULE>.md` |
| `<PROJECT>/models/*.<ext>` | `<YOUR_VAULT_FOLDER>/database-schema.md` |
| `<PROJECT>/migrations/*` | `<YOUR_VAULT_FOLDER>/database-schema.md` |
| `<PROJECT>/tasks/*.<ext>` (background) | `<YOUR_VAULT_FOLDER>/architecture.md` |
| `<PROJECT>/config.<ext>` | `<YOUR_VAULT_FOLDER>/local-development.md` |
| `Dockerfile` / `docker-compose.yml` | `<YOUR_VAULT_FOLDER>/deployment.md` |
| `requirements.txt` / `package.json` | `<YOUR_VAULT_FOLDER>/tech-stack.md` |

## Frontend code → documentation

| Change in | Update |
|---|---|
| `<PROJECT>/src/pages/<YOUR_MODULE>/*` | `<YOUR_VAULT_FOLDER>/features/<YOUR_MODULE>.md` |
| `<PROJECT>/src/components/layout/*` | `<YOUR_VAULT_FOLDER>/frontend-guide.md` |
| `<PROJECT>/src/i18n/*.json` | `<YOUR_VAULT_FOLDER>/i18n-guide.md` |
| `<PROJECT>/src/config/branding.*` | `<YOUR_VAULT_FOLDER>/branding.md` |
| `<PROJECT>/src/api/client.*` | `<YOUR_VAULT_FOLDER>/frontend-guide.md` |

## Permissions / Roles / Users

| Change | Update |
|---|---|
| New permission in the DB | `<YOUR_VAULT_FOLDER>/permissions.md` |
| New role | `<YOUR_VAULT_FOLDER>/permissions.md` |
| Change to a role's permission grants | `<YOUR_VAULT_FOLDER>/permissions.md` |

## Configuration / Infra

| Change | Update |
|---|---|
| `~/.claude/settings.json` | `<YOUR_VAULT_FOLDER>/setup.md` |
| `.env` variables | `<YOUR_VAULT_FOLDER>/local-development.md` + deployment.md |
| Backup procedure / cron | `<YOUR_VAULT_FOLDER>/infrastructure.md` |
| External integrations | `<YOUR_VAULT_FOLDER>/integrations.md` |

## KRONOS Workflow Engine (meta)

| Change | Update |
|---|---|
| `KRONOS.md` | (this is the documentation) |
| `KRONOS-ROUTING.md` | (this file — maintained by hand) |
| `hooks/check-workflow.{sh,py}` | `KRONOS.md` (the hook section) |
| `skills/kronos-*/SKILL.md` | `KRONOS.md` (the commands section) |

## Wildcards / fallback

If a change is **not covered** by this table → the Discovery Agent (Grep over the vault) finds relevant files by keys (function names, endpoints, classes).

If Discovery finds nothing either → the final Sanity Check reports "maybe forgot to document X, Y".
