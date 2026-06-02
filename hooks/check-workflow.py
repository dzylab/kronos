#!/usr/bin/env python3
"""KRONOS Workflow Engine — PreToolUse hook (Python, Phase 3).

5 stages: PLAN -> CODE -> TEST -> DOCS -> COMMIT

PreToolUse hook contract:
    stdin:  JSON {session_id, cwd, tool_name, tool_input.command, ...}
    exit 0: PASS
    exit 2: BLOCK (stderr -> surfaced to the agent as an error)

Logic:
    a) read-only git (status/log/diff WITHOUT commit) -> PASS
    b) KRONOS_BYPASS=1 -> PASS + record an entry in the Decisions log
    c) git commit / git push -> independent verification of WORKFLOW.md (5 stages)
    d) everything else -> PASS
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import shutil

# Windows: force UTF-8 for stdin/stdout/stderr (unicode-safe)
if sys.platform == "win32":
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # Python < 3.7 fallback (should not happen)
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


# ──────────────────── WORKFLOW.md parsing ────────────────────

STAGE_RE = re.compile(
    r"^\-\s+\[(?P<mark>.)\]\s+(?P<num>\d+)\.\s+\*\*(?P<name>[A-Z]+)\*\*",
    re.MULTILINE,
)
TASK_RE = re.compile(r"^\*\*Task:\*\*\s*(.*?)$", re.MULTILINE)
SLUG_RE = re.compile(r"^\*\*Slug:\*\*\s*(.*?)$", re.MULTILINE)
TYPE_RE = re.compile(r"^\*\*Type:\*\*\s*(.*?)$", re.MULTILINE)
HASH_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
# Anchored: the WHOLE field equals a single <...> token (not a substring). A real
# name like "Refactor <Header>" / "<A> and <B>" does NOT match (text outside one token).
PLACEHOLDER_RE = re.compile(r"^\s*<[^>]+>\s*$")
SECTION_RE_FMT = r"(?ms)^##\s+{title}\s*\n(.*?)(?=^##\s+|\Z)"

# Minimum line requirements
MIN_PLAN_LINES = 50
MIN_TEST_LOG_LINES = 5


# ──────────────────── Config: paths (env-driven, portable core) ────────────────────
# Concrete paths are NOT hardcoded in the .py — they come from env (KRONOS sets them in
# check-workflow.sh; the public twin sets them in install.sh). This keeps the core
# portable/shared, while locale specifics live in the gitignored wrapper. Fallback is a
# cwd-relative heuristic (hermetic: self-test clears env -> real repos/vault untouched).

def _expand(path_str: str) -> Path:
    """Expand ~ and $VAR in a path."""
    return Path(os.path.expanduser(os.path.expandvars(path_str)))


def get_extra_repos(cwd: Path) -> list[Path]:
    """Extra repositories to check for a diff during CODE (submodules etc.) from
    KRONOS_REPOS (comma-separated). Relative names are joined with the project root (cwd)."""
    repos: list[Path] = []
    for chunk in os.environ.get("KRONOS_REPOS", "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        p = _expand(chunk)
        if not p.is_absolute():
            p = cwd / p
        repos.append(p)
    return repos


def get_vault_path(cwd: Path) -> Optional[Path]:
    """Documentation directory (Obsidian vault). VAULT_PATH env first, then a cwd heuristic."""
    env = os.environ.get("VAULT_PATH", "").strip()
    if env:
        p = _expand(env)
        if p.exists():
            return p
    for name in ("vault", "docs", "wiki"):
        cand = cwd.parent / name
        if cand.exists():
            return cand
    return None


def _is_placeholder(value: str) -> bool:
    """True if the field value is a template sentinel, not real content.

    Fires on: empty; the WHOLE field is a single `<...>` token (anchored ^...$,
    PLACEHOLDER_RE, language-agnostic); an unfilled bold heading (`**...`); bare
    placeholder words (task / name / slug). Matches against the WHOLE field, NOT a
    substring — a real task name with angle brackets inside (e.g. "Refactor <Header>
    component") is NOT treated as a template -> a live workflow still gets verified."""
    v = (value or "").strip()
    if not v:
        return True
    if v.startswith("**"):
        return True
    if PLACEHOLDER_RE.match(v):
        return True
    if v.lower() in ("task", "name", "slug"):
        return True
    return False


def read_workflow(wf_path: Path) -> Optional[dict]:
    """Return {task, slug, type, stages: [...], text, sections: {title: body}} or None."""
    if not wf_path.exists():
        return None
    text = wf_path.read_text(encoding="utf-8", errors="replace")
    task_m = TASK_RE.search(text)
    slug_m = SLUG_RE.search(text)
    type_m = TYPE_RE.search(text)
    task = task_m.group(1).strip() if task_m else ""
    slug = slug_m.group(1).strip() if slug_m else ""
    task_type = (type_m.group(1).strip().upper() if type_m else "") or "MEDIUM"
    # Template / placeholder state of WORKFLOW.md -> there is NO active workflow.
    # After a workflow is archived the file is reset to the TEMPLATE: Task = a <...>
    # placeholder (or empty), stages [ ]. Such a commit is NOT blocked — otherwise every
    # commit would be falsely blocked. Match BY PATTERN <...> (anchored, _is_placeholder),
    # NOT by substring: a real name "Refactor <Header>" / "<A> and <B>" is a live workflow.
    if _is_placeholder(task):
        return None
    if _is_placeholder(slug) or "TRIVIAL / MEDIUM" in slug:
        return None
    stages = []
    for m in STAGE_RE.finditer(text):
        mark = m.group("mark").lower()
        # "x" = done, "⊘" = skipped (also OK), " " = pending, "⏳" = in progress
        done = mark == "x"
        skipped = mark == "⊘"
        stages.append({
            "num": int(m.group("num")),
            "name": m.group("name"),
            "done": done,
            "skipped": skipped,
            "mark": mark,
            "closed": done or skipped,  # used to check "is a commit allowed"
        })
    # Extract sections for TEST/DOCS verification
    sections = {}
    for title in ("Test log", "Docs updated", "Activity log", "Decisions log"):
        sec_re = re.compile(SECTION_RE_FMT.format(title=re.escape(title)), re.MULTILINE | re.DOTALL)
        sec_m = sec_re.search(text)
        if sec_m:
            body = sec_m.group(1).strip()
            sections[title] = body
        else:
            sections[title] = ""
    return {
        "task": task,
        "slug": slug,
        "type": task_type,
        "stages": stages,
        "text": text,
        "sections": sections,
    }


# ──────────────────── Independent stage verification ────────────────────

def verify_plan(cwd: Path, slug: str) -> Optional[str]:
    """PLAN [x] = plans/<slug>.md exists & wc -l ≥ MIN_PLAN_LINES."""
    if not slug:
        return "PLAN[x] but Slug is empty in WORKFLOW.md"
    plan_file = cwd / "plans" / f"{slug}.md"
    if not plan_file.exists():
        return f"PLAN[x] but plans/{slug}.md does not exist"
    line_count = sum(1 for _ in plan_file.open(encoding="utf-8", errors="replace"))
    if line_count < MIN_PLAN_LINES:
        return f"PLAN[x] but plans/{slug}.md has only {line_count} lines (need >={MIN_PLAN_LINES})"
    return None


def _has_changes_in(repo: Path) -> Optional[bool]:
    """True if the repo has staged/unstaged changes; False if clean;
    None if the repo is unavailable (no git, no directory)."""
    if not repo.exists():
        return None
    try:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo, capture_output=True, timeout=10,
        ).returncode
        unstaged = subprocess.run(
            ["git", "diff", "--quiet"],
            cwd=repo, capture_output=True, timeout=10,
        ).returncode
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return staged != 0 or unstaged != 0


def verify_code(cwd: Path, is_push: bool) -> Optional[str]:
    """CODE [x] = staged/unstaged changes in AT LEAST ONE tracked repo:
    the main project (cwd), an extra repo (submodule), or the docs vault.
    For push the commit is already done — skip."""
    if is_push:
        return None
    repos = [cwd] + get_extra_repos(cwd)
    vault = get_vault_path(cwd)
    if vault is not None:
        repos.append(vault)
    saw_any_repo = False
    for repo in repos:
        has = _has_changes_in(repo)
        if has is None:
            continue
        saw_any_repo = True
        if has:
            return None  # at least one repo has a diff — the stage is valid
    if not saw_any_repo:
        # None of the repos are available — do not block (unusual environment)
        return None
    return "CODE[x] but NONE of the tracked repos (main / extra repo / docs vault) has staged/unstaged changes"


def verify_test(sections: dict) -> Optional[str]:
    """TEST [x] = the '## Test log' section has >= MIN_TEST_LOG_LINES lines of real output."""
    body = sections.get("Test log", "")
    if not body:
        return f"TEST[x] but the '## Test log' section is empty"
    # Count non-empty lines except HTML comments
    real_lines = [
        ln for ln in body.splitlines()
        if ln.strip() and not ln.strip().startswith("<!--")
    ]
    if len(real_lines) < MIN_TEST_LOG_LINES:
        return f"TEST[x] but '## Test log' has only {len(real_lines)} lines (need >={MIN_TEST_LOG_LINES})"
    return None


def verify_docs(cwd: Path, sections: dict) -> Optional[str]:
    """DOCS [x] = the '## Docs updated' section lists files + git status of the docs vault shows modified.

    The list in the section holds relative paths to docs/vault files.
    """
    body = sections.get("Docs updated", "")
    if not body:
        return "DOCS[x] but the '## Docs updated' section is empty"
    listed = [
        ln.strip("- *\t ")
        for ln in body.splitlines()
        if ln.strip() and not ln.strip().startswith("<!--")
    ]
    if not listed:
        return "DOCS[x] but '## Docs updated' has no file list"

    # Verify the docs vault has real changes
    vault = get_vault_path(cwd)
    if vault is None:
        # Vault not found — do not block (the project may have no vault)
        return None
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=vault, capture_output=True, timeout=10, text=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    # If nothing is modified — there are no real doc changes
    modified = [ln for ln in result.stdout.splitlines() if ln.strip()]
    if not modified:
        # Note: docs might already be committed in a separate commit. Kept strict for now:
        return f"DOCS[x] but the docs vault has no modified/new files (git status empty)"
    return None


def verify_commit(text: str, is_push: bool) -> Optional[str]:
    """COMMIT [x] = WORKFLOW.md contains a 7+ hex git hash."""
    if not HASH_RE.search(text):
        return "COMMIT[x] but no commit hash (7+ hex chars) in the WORKFLOW.md Activity log"
    return None


# ──────────────────── WATCHDOG: hard heartbeat check (Phase B) ────────────────────
# Goal: you cannot mark a stage "done [x]" that in fact NEVER STARTED (no STARTED
# trace in WORKFLOW.md). This is a HARD check: it BLOCKS the commit (exit 2). Active
# ONLY if the workflow uses heartbeat discipline (a '## Heartbeat' section exists). A
# workflow without it is fully backward-compatible.

HEARTBEAT_SECTION_RE = re.compile(r"(?im)^##\s+Heartbeat\b")
# The whole '## Heartbeat' section block (up to the next '## ' or end of file).
HEARTBEAT_BLOCK_RE = re.compile(r"(?ims)^##\s+Heartbeat\b.*?(?=^##\s+|\Z)")
# Markers that a stage was started/worked (Activity style): an auto STARTED OR a
# human-readable transition. -> / ⏳ / ✅ are language-neutral, done/in progress are English.
_STAGE_MARKER = r"(?:STARTED|done|→|⏳|✅|in[ -]?progress)"
# A real STARTED timestamp (NOT the "-" placeholder): require a YYYY-MM-DD date.
_REAL_STARTED_RE = re.compile(r"(?im)^\s*[-*]?\s*STARTED\s*:\s*\S*\d{4}-\d{2}-\d{2}")


def heartbeat_enabled(text: str) -> bool:
    """True if WORKFLOW.md contains a '## Heartbeat' section (watchdog discipline)."""
    return bool(HEARTBEAT_SECTION_RE.search(text))


def _stage_started_trace(text: str, name: str) -> bool:
    """True if there is evidence that stage <name> ACTUALLY started/was worked.

    Accept ANY of (in decreasing strength):
      • Activity style (any line): "STAGE <NAME> STARTED" (auto /kronos-next) OR
        "STAGE <NAME>" + a transition marker (STARTED|done|→|⏳|✅|in progress) —
        what a careful MANUAL run writes;
      • Heartbeat block: the CURRENT stage "STAGE: <NAME>" + a real "STARTED: <date>"
        (not the "-" placeholder). Closes the old docstring-vs-behavior gap:
        a filled Heartbeat now counts;
      • legacy "<NAME> STARTED".

    Does NOT match the stage checklist ("- [x] 2. **CODE**" -> that is "**CODE**",
    not "STAGE CODE") and does NOT match the heartbeat line "STAGE: <NAME>" via the
    Activity branch (the colon breaks \\s+) — the Heartbeat counts ONLY with a real
    STARTED date. So a truly "blind" [x] (no trace anywhere) still blocks the commit —
    that is the signal we want.
    """
    n = re.escape(name)
    # (a) "STAGE <NAME>" + a start/transition marker on ONE line (Activity style)
    if re.search(rf"(?im)^.*\bSTAGE\s+{n}\b.*{_STAGE_MARKER}.*$", text):
        return True
    # legacy "<NAME> STARTED"
    if re.search(rf"(?im)\b{n}\s+STARTED\b", text):
        return True
    # (b) Heartbeat block: STAGE: <NAME> + a real STARTED: <date> (in the same block)
    hb = HEARTBEAT_BLOCK_RE.search(text)
    if hb:
        block = hb.group(0)
        if re.search(rf"(?im)^\s*[-*]?\s*STAGE\s*:\s*{n}\b", block) and _REAL_STARTED_RE.search(block):
            return True
    return False


def verify_heartbeat(wf: dict) -> list[str]:
    """HARD (BLOCKS the commit): every [x] stage of a heartbeat workflow — EXCEPT PLAN —
    must have a STARTED trace, otherwise you could mark a stage [x] without ever running it.
    Returns a list of errors (added to the blocking `errors` set in run_hook).
    If heartbeat is not enabled — returns [] (backward compatibility: legacy workflows
    without a '## Heartbeat' section are NOT gated). ⊘ skipped / [ ] / ⏳ stages do not
    need a trace. PLAN is exempt: it is auto-started by the workflow-creation step and its
    authenticity is already gated independently by verify_plan (the plans/<slug>.md artifact
    must be >= MIN_PLAN_LINES), so a separate STARTED trace would be redundant.
    KRONOS_BYPASS=1 bypasses the whole hook (recorded in the Decisions log)."""
    text = wf.get("text", "")
    if not heartbeat_enabled(text):
        return []
    errors: list[str] = []
    for stage in wf.get("stages", []):
        if not stage.get("done"):
            continue  # ⊘ skipped / [ ] / ⏳ — STARTED not required
        name = stage["name"]
        if name.upper() == "PLAN":
            continue  # PLAN is auto-started by workflow creation and gated by verify_plan
                      # (artifact file) — a separate STARTED trace is redundant.
        if not _stage_started_trace(text, name):
            errors.append(
                f"{name}[x] is marked done but has no STARTED trace "
                f"(the heartbeat did not record the stage start — the stage may not have run)"
            )
    return errors


# ──────────────────── BYPASS recording ────────────────────

def record_bypass(wf_path: Path, command: str) -> None:
    """Append an entry to the Decisions log."""
    text = wf_path.read_text(encoding="utf-8", errors="replace")
    offset = int(os.environ.get("KRONOS_LOG_TZ_OFFSET", "0"))  # default 0 = UTC
    tz = timezone(timedelta(hours=offset))
    ts = datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S%z")
    cmd_short = command.replace("\n", " ")[:120]
    record = f"\n- {ts} **BYPASS used**, command: `{cmd_short}`"

    if "## Decisions log" in text:
        new_text = re.sub(
            r"(^## Decisions log\s*\n)",
            r"\1" + record + "\n",
            text,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        new_text = text.rstrip() + "\n\n## Decisions log\n" + record + "\n"
    wf_path.write_text(new_text, encoding="utf-8")


# ──────────────────── Main hook entrypoint ────────────────────

READ_ONLY_PATTERNS = [
    r"\bgit\s+status\b",
    r"\bgit\s+log\b",
    r"\bgit\s+diff\b",
    r"\bgit\s+show\b",
    r"\bgit\s+branch\b",
    r"\bgit\s+remote\b",
    r"\bgit\s+rev-parse\b",
    r"\bgit\s+config\s+--get\b",
]


def classify(command: str) -> str:
    """commit / push / readonly / other."""
    if re.search(r"\bgit\s+commit\b", command):
        return "commit"
    if re.search(r"\bgit\s+push\b", command):
        return "push"
    for pat in READ_ONLY_PATTERNS:
        if re.search(pat, command):
            return "readonly"
    return "other"


# Which stages are NOT required to be closed BEFORE git commit
# (COMMIT may be open — we are committing right now)
STAGES_OPTIONAL_BEFORE_COMMIT = {"COMMIT"}


def run_hook(payload: dict) -> int:
    # PROJECT_PATH (optional) overrides the project root; otherwise use the payload cwd.
    # Supports ~ and $VAR. Lets you point the hook at a specific project (monorepo, or git
    # invoked from a subdirectory) instead of relying on the command's working directory.
    _pp = os.environ.get("PROJECT_PATH", "").strip()
    cwd = _expand(_pp) if _pp else Path(payload.get("cwd", os.getcwd()))
    tool_input = payload.get("tool_input", {}) or {}
    command = tool_input.get("command", "") or ""

    kind = classify(command)

    if kind == "readonly":
        return 0
    if kind == "other":
        return 0

    is_push = kind == "push"
    wf_path = cwd / "WORKFLOW.md"

    # (b) KRONOS_BYPASS=1
    if os.environ.get("KRONOS_BYPASS") == "1":
        if wf_path.exists():
            try:
                record_bypass(wf_path, command)
            except Exception as e:
                print(f"[kronos] Warning: failed to record BYPASS: {e}", file=sys.stderr)
        return 0

    # (c) Verification
    wf = read_workflow(wf_path)
    if wf is None:
        return 0  # no workflow -> not a KRONOS-managed project

    errors: list[str] = []
    for stage in wf["stages"]:
        name = stage["name"]
        done = stage["done"]
        skipped = stage["skipped"]
        closed = stage["closed"]
        mark = stage["mark"]

        if done:
            # actual fact verification
            if name == "PLAN":
                err = verify_plan(cwd, wf["slug"])
            elif name == "CODE":
                err = verify_code(cwd, is_push)
            elif name == "TEST":
                err = verify_test(wf["sections"])
            elif name == "DOCS":
                err = verify_docs(cwd, wf["sections"])
            elif name == "COMMIT":
                err = verify_commit(wf["text"], is_push)
            else:
                err = None
            if err:
                errors.append(err)
        elif skipped:
            # ⊘ = skipped. A Decisions log entry must exist
            decisions = wf["sections"].get("Decisions log", "")
            pattern = re.compile(
                rf"SKIPPED\s+stage\s+{stage['num']}|skipped\s+{name}",
                re.IGNORECASE,
            )
            if not pattern.search(decisions):
                errors.append(
                    f"{name} is marked ⊘ skipped but has no 'SKIPPED stage {stage['num']}: <reason>' entry in the Decisions log"
                )
        else:
            # not closed (mark = " " or "⏳")
            if name in STAGES_OPTIONAL_BEFORE_COMMIT and not is_push:
                # COMMIT may be open right before git commit — that is fine
                continue
            if mark in (" ", ""):
                errors.append(f"{name} is not closed ([ ]). /kronos-next, /kronos-skip <reason>, or KRONOS_BYPASS=1.")
            elif mark == "⏳":
                errors.append(f"{name} is in progress (⏳). Close the stage or /kronos-skip.")

    # WATCHDOG (HARD): a [x] stage without a STARTED trace BLOCKS the commit — you cannot
    # mark a stage done without running it. Legacy (no '## Heartbeat') is exempt; ⊘ / [ ] / ⏳
    # do not need a trace; KRONOS_BYPASS=1 bypasses the whole hook.
    errors.extend(verify_heartbeat(wf))

    if errors:
        print("🚫 KRONOS hook blocked the command:\n", file=sys.stderr)
        for e in errors:
            print(f"  • {e}", file=sys.stderr)
        print(f"\nWORKFLOW.md: {wf_path}", file=sys.stderr)
        print(f"Task: {wf['task']}", file=sys.stderr)
        if wf["slug"]:
            print(f"Slug: {wf['slug']} (Type: {wf['type']})", file=sys.stderr)
        print("\nOptions:", file=sys.stderr)
        print("  • /kronos-next — close the open stage", file=sys.stderr)
        print("  • /kronos-skip <stage> <reason> — skip (⊘ + record)", file=sys.stderr)
        print(f"  • KRONOS_BYPASS=1 <command> — bypass (recorded in the Decisions log)", file=sys.stderr)
        return 2

    return 0


# ──────────────────── Self-test ────────────────────

def self_test() -> int:
    """Create a temp git repo + temp vault, run the test cases
    (exit-code cases + BYPASS-record + watchdog heartbeat hard-gate checks, Phase B).
    Includes a negative case: a live <...> in a task name is NOT treated as a template."""
    tmpdir = tempfile.mkdtemp(prefix="kronos_selftest_")
    vault_dir = tempfile.mkdtemp(prefix="kronos_vault_")
    # Hermetic: drop real paths from env so the test does not touch the real vault/submodule.
    _saved_env = {k: os.environ.pop(k, None) for k in ("VAULT_PATH", "KRONOS_REPOS", "PROJECT_PATH")}
    try:
        cwd = Path(tmpdir)
        vault = Path(vault_dir)
        # init the project git repo
        subprocess.run(["git", "init", "-q"], cwd=cwd, check=True)
        subprocess.run(["git", "config", "user.email", "selftest@kronos.local"], cwd=cwd, check=True)
        subprocess.run(["git", "config", "user.name", "KRONOS Selftest"], cwd=cwd, check=True)
        (cwd / "init.txt").write_text("init")
        subprocess.run(["git", "add", "init.txt"], cwd=cwd, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=cwd, check=True, capture_output=True)

        # init vault repo
        subprocess.run(["git", "init", "-q"], cwd=vault, check=True)
        subprocess.run(["git", "config", "user.email", "selftest@kronos.local"], cwd=vault, check=True)
        subprocess.run(["git", "config", "user.name", "KRONOS Selftest"], cwd=vault, check=True)
        (vault / "init.md").write_text("init")
        subprocess.run(["git", "add", "init.md"], cwd=vault, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=vault, check=True, capture_output=True)

        # Monkey-patch verify_docs vault search to use our tmp vault
        global verify_docs
        original_verify_docs = verify_docs

        def patched_verify_docs(cwd_arg: Path, sections: dict) -> Optional[str]:
            # like the original, but with an explicit vault path
            body = sections.get("Docs updated", "")
            if not body:
                return "DOCS[x] but the '## Docs updated' section is empty"
            listed = [ln.strip("- *\t ") for ln in body.splitlines()
                      if ln.strip() and not ln.strip().startswith("<!--")]
            if not listed:
                return "DOCS[x] but '## Docs updated' has no file list"
            try:
                result = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=vault, capture_output=True, timeout=10, text=True,
                )
            except Exception:
                return None
            modified = [ln for ln in result.stdout.splitlines() if ln.strip()]
            if not modified:
                return f"DOCS[x] but the docs vault has no modified/new files"
            return None
        verify_docs = patched_verify_docs

        passed = 0
        failed = 0

        def run_case(name: str, expected: int, payload: dict, env_extra: dict | None = None) -> int:
            nonlocal passed, failed
            old_env = {}
            env = env_extra or {}
            for k, v in env.items():
                old_env[k] = os.environ.get(k)
                os.environ[k] = v
            try:
                rc = run_hook(payload)
            finally:
                for k, v in old_env.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
            if rc == expected:
                print(f"  [OK]   PASS: {name} (exit={rc})")
                passed += 1
            else:
                print(f"  [FAIL] FAIL: {name} (expected={expected}, got={rc})")
                failed += 1
            return rc

        print(f"=== KRONOS hook self-test (5 stages) ===")
        print(f"    project: {tmpdir}")
        print(f"    vault:   {vault_dir}")

        # Baseline "all open" — for negative cases
        base_wf = lambda: (cwd / "WORKFLOW.md").write_text(
            "# Active Workflow\n\n"
            "**Task:** test\n**Slug:** s\n**Type:** MEDIUM\n\n"
            "## Stages\n\n"
            "- [ ] 1. **PLAN** → x\n"
            "- [ ] 2. **CODE** → x\n"
            "- [ ] 3. **TEST** → x\n"
            "- [ ] 4. **DOCS** → x\n"
            "- [ ] 5. **COMMIT** → x\n\n"
            "## Test log\n\n## Docs updated\n\n## Activity log\n\n## Decisions log\n",
            encoding="utf-8",
        )

        # 1. all open → block
        base_wf()
        run_case("all open → blocks commit", 2,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m test"}})

        # 2. read-only git status → passes
        run_case("git status passes", 0,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git status"}})

        # 3. PowerShell + commit → blocks (matcher cross-shell)
        run_case("PowerShell + commit blocks", 2,
                 {"cwd": str(cwd), "tool_name": "PowerShell",
                  "tool_input": {"command": "git commit -m ps"}})

        # 4. BYPASS=1 → pass + write
        run_case("BYPASS pass", 0,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m bypass"}},
                 env_extra={"KRONOS_BYPASS": "1"})
        wf_text = (cwd / "WORKFLOW.md").read_text(encoding="utf-8")
        if "BYPASS used" in wf_text:
            print("  [OK]   PASS: BYPASS recorded in Decisions log")
            passed += 1
        else:
            print("  [FAIL] FAIL: BYPASS NOT recorded")
            failed += 1

        # 5. PLAN[x] forged — no file
        (cwd / "WORKFLOW.md").write_text(
            "**Task:** t\n**Slug:** fake-slug\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → fake\n"
            "- [ ] 2. **CODE** → x\n"
            "- [ ] 3. **TEST** → x\n"
            "- [ ] 4. **DOCS** → x\n"
            "- [ ] 5. **COMMIT** → x\n\n"
            "## Test log\n## Docs updated\n## Activity log\n## Decisions log\n",
            encoding="utf-8",
        )
        run_case("PLAN[x] without file → blocks", 2,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m fake"}})

        # 6. PLAN[x] file exists but < 50 lines
        (cwd / "plans").mkdir(exist_ok=True)
        (cwd / "plans" / "short-slug.md").write_text("\n".join(f"l{i}" for i in range(30)))
        (cwd / "WORKFLOW.md").write_text(
            "**Task:** t\n**Slug:** short-slug\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → ok\n"
            "- [ ] 2. **CODE** → x\n"
            "- [ ] 3. **TEST** → x\n"
            "- [ ] 4. **DOCS** → x\n"
            "- [ ] 5. **COMMIT** → x\n\n"
            "## Test log\n## Docs updated\n## Activity log\n## Decisions log\n",
            encoding="utf-8",
        )
        run_case("PLAN[x] short file (<50) → blocks", 2,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m short"}})

        # 7. TEST[x] but Test log < 5 lines
        (cwd / "plans" / "okslug.md").write_text("\n".join(f"l{i}" for i in range(60)))
        (cwd / "newfile.txt").write_text("change")
        subprocess.run(["git", "add", "newfile.txt"], cwd=cwd, check=True)
        (cwd / "WORKFLOW.md").write_text(
            "**Task:** t\n**Slug:** okslug\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → ok\n"
            "- [x] 2. **CODE** → ok\n"
            "- [x] 3. **TEST** → fake\n"
            "- [ ] 4. **DOCS** → x\n"
            "- [ ] 5. **COMMIT** → x\n\n"
            "## Test log\n\nonly one line\n\n"
            "## Docs updated\n## Activity log\n## Decisions log\n",
            encoding="utf-8",
        )
        run_case("TEST[x] short log (<5) → blocks", 2,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m test"}})

        # 8. DOCS[x] but vault not modified
        # rewrite WORKFLOW with TEST log >= 5 lines
        (cwd / "WORKFLOW.md").write_text(
            "**Task:** t\n**Slug:** okslug\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → ok\n"
            "- [x] 2. **CODE** → ok\n"
            "- [x] 3. **TEST** → ok\n"
            "- [x] 4. **DOCS** → fake\n"
            "- [ ] 5. **COMMIT** → x\n\n"
            "## Test log\nline 1\nline 2\nline 3\nline 4\nline 5\nline 6\n\n"
            "## Docs updated\n- 10-Developer-Docs/08-API-Reference.md\n\n"
            "## Activity log\n## Decisions log\n",
            encoding="utf-8",
        )
        # vault clean — nothing modified
        run_case("DOCS[x] but vault clean → blocks", 2,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m fake-docs"}})

        # 9. DOCS[x] and vault really modified → passes
        (vault / "10-Developer-Docs").mkdir(exist_ok=True)
        (vault / "10-Developer-Docs" / "08-API-Reference.md").write_text("real update")
        run_case("DOCS[x] + vault modified → passes commit", 0,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m real"}})

        # 10. SKIPPED stage via ⊘ + a Decisions log record
        (cwd / "WORKFLOW.md").write_text(
            "**Task:** t\n**Slug:** okslug\n**Type:** TRIVIAL\n\n"
            "- [⊘] 1. **PLAN** → skip\n"
            "- [x] 2. **CODE** → ok\n"
            "- [⊘] 3. **TEST** → skip\n"
            "- [x] 4. **DOCS** → ok\n"
            "- [ ] 5. **COMMIT** → x\n\n"
            "## Test log\n## Docs updated\n- file.md\n\n"
            "## Activity log\n## Decisions log\n"
            "- SKIPPED stage 1: TRIVIAL task\n"
            "- SKIPPED stage 3: TRIVIAL task\n",
            encoding="utf-8",
        )
        run_case("⊘ skipped with reason → passes", 0,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m trivial"}})

        # 11. SKIPPED but no Decisions record → blocks
        (cwd / "WORKFLOW.md").write_text(
            "**Task:** t\n**Slug:** okslug\n**Type:** TRIVIAL\n\n"
            "- [⊘] 1. **PLAN** → skip\n"
            "- [x] 2. **CODE** → ok\n"
            "- [x] 3. **TEST** → ok\n"
            "- [x] 4. **DOCS** → ok\n"
            "- [ ] 5. **COMMIT** → x\n\n"
            "## Test log\nl1\nl2\nl3\nl4\nl5\nl6\n\n## Docs updated\n- f.md\n\n"
            "## Activity log\n## Decisions log\n(no skip record)\n",
            encoding="utf-8",
        )
        run_case("⊘ skipped without record → blocks", 2,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m no-reason"}})

        # 12b. A live <...> INSIDE a task name is NOT treated as a template (anchored).
        # Task "Refactor <Header> component" is a real workflow, not a template:
        # verification MUST run → a fake PLAN[x] without a file → BLOCK.
        # Proves a <...> substring does not punch through the gate.
        (cwd / "WORKFLOW.md").write_text(
            "**Task:** Refactor <Header> component\n**Slug:** live-angle-slug\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → fake (no plans/live-angle-slug.md)\n"
            "- [ ] 2. **CODE** → x\n"
            "- [ ] 3. **TEST** → x\n"
            "- [ ] 4. **DOCS** → x\n"
            "- [ ] 5. **COMMIT** → x\n\n"
            "## Test log\n## Docs updated\n## Activity log\n## Decisions log\n",
            encoding="utf-8",
        )
        run_case("live <...> in task name → NOT template → blocks fake PLAN", 2,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m angle"}})

        # 12. no WORKFLOW.md → passes
        (cwd / "WORKFLOW.md").unlink()
        run_case("no WORKFLOW.md → passes", 0,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m no-wf"}})

        # ── WATCHDOG heartbeat self-tests (direct helper call; non-empty list = BLOCKS commit) ──
        def assert_block(name: str, wf_text: str, expect_block: bool) -> None:
            nonlocal passed, failed
            wf_obj = {"text": wf_text, "stages": []}
            for m in STAGE_RE.finditer(wf_text):
                mk = m.group("mark").lower()
                wf_obj["stages"].append({
                    "num": int(m.group("num")), "name": m.group("name"),
                    "done": mk == "x", "skipped": mk == "⊘", "mark": mk,
                    "closed": mk in ("x", "⊘"),
                })
            errs = verify_heartbeat(wf_obj)  # HARD: non-empty → these block the commit
            got = len(errs) > 0
            if got == expect_block:
                print(f"  [OK]   PASS: {name} (block-errors={len(errs)})")
                passed += 1
            else:
                print(f"  [FAIL] FAIL: {name} (expect_block={expect_block}, got={len(errs)})")
                failed += 1

        # 13. heartbeat ON + [x] CODE WITHOUT a STARTED trace → blocks
        assert_block("heartbeat ON, [x] without STARTED → blocks", (
            "**Task:** t\n**Slug:** s\n**Type:** LARGE\n\n"
            "- [x] 1. **PLAN** → ok\n- [x] 2. **CODE** → ok\n"
            "- [ ] 3. **TEST** → x\n\n"
            "## Heartbeat\n- STAGE: CODE\n- STARTED: -\n\n"
            "## Activity log\n- 2026-05-30 STAGE PLAN STARTED\n- PLAN ✅\n"
        ), expect_block=True)  # PLAN has a trace, CODE does not → 1 block-error

        # 14. heartbeat ON + all [x] have a STARTED trace → no block
        assert_block("heartbeat ON, all STARTED → no block", (
            "**Task:** t\n**Slug:** s\n**Type:** LARGE\n\n"
            "- [x] 1. **PLAN** → ok\n- [x] 2. **CODE** → ok\n"
            "- [ ] 3. **TEST** → x\n\n"
            "## Heartbeat\n- STAGE: TEST\n- STARTED: 2026-05-30T18:00\n\n"
            "## Activity log\n- STAGE PLAN STARTED\n- STAGE CODE STARTED\n"
        ), expect_block=False)

        # 15. heartbeat OFF (no section) → backward compatibility, no block
        assert_block("heartbeat OFF (legacy) → no block", (
            "**Task:** t\n**Slug:** s\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → ok\n- [x] 2. **CODE** → ok\n\n"
            "## Activity log\n- PLAN done\n"
        ), expect_block=False)

        # 16. FIX 2026-05-31: a filled Heartbeat (STAGE:CODE + a real STARTED:date)
        #     counts as a CODE trace even WITHOUT a "STAGE CODE STARTED" Activity line.
        assert_block("heartbeat filled (STAGE+real STARTED) → no block", (
            "**Task:** t\n**Slug:** s\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → ok\n- [x] 2. **CODE** → ok\n- [ ] 3. **TEST** → x\n\n"
            "## Heartbeat\n- STAGE: CODE\n- STARTED: 2026-05-31T10:00\n\n"
            "## Activity log\n- STAGE PLAN STARTED\n"
        ), expect_block=False)

        # 17. FIX 2026-05-31: a human-readable transition "STAGE CODE → done" (manual run)
        #     counts as a trace.
        assert_block("activity transition 'STAGE X done' → no block", (
            "**Task:** t\n**Slug:** s\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → ok\n- [x] 2. **CODE** → ok\n- [ ] 3. **TEST** → x\n\n"
            "## Heartbeat\n- STAGE: TEST\n- STARTED: 2026-05-31T11:00\n\n"
            "## Activity log\n- STAGE PLAN STARTED\n- STAGE CODE done\n"
        ), expect_block=False)

        # 18. NEGATIVE (guard against over-relaxation): a truly "blind" [x] CODE —
        #     zero traces (heartbeat on ANOTHER stage, no CODE mention in Activity) →
        #     the block MUST remain.
        assert_block("blind [x] (no trace anywhere) → still blocks", (
            "**Task:** t\n**Slug:** s\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → ok\n- [x] 2. **CODE** → ok\n- [ ] 3. **TEST** → x\n\n"
            "## Heartbeat\n- STAGE: PLAN\n- STARTED: 2026-05-31T09:00\n\n"
            "## Activity log\n- STAGE PLAN STARTED\n"
        ), expect_block=True)

        # 18b. PLAN EXEMPTION: PLAN [x] with NO PLAN trace anywhere, but CODE [x] HAS a trace.
        #      PLAN is auto-started by workflow creation and gated by verify_plan (artifact),
        #      so it needs no STARTED trace → must NOT block. CODE still requires its trace.
        assert_block("PLAN [x] without trace is exempt (CODE has trace) → no block", (
            "**Task:** t\n**Slug:** s\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → ok\n- [x] 2. **CODE** → ok\n- [ ] 3. **TEST** → x\n\n"
            "## Heartbeat\n- STAGE: CODE\n- STARTED: 2026-05-31T10:00\n\n"
            "## Activity log\n- STAGE CODE STARTED\n"
        ), expect_block=False)

        # 19. HARD end-to-end (Phase B): heartbeat workflow, ALL [x] have a STARTED trace +
        #     artifacts valid (plans/okslug.md 60 lines, diff staged, vault modified) → PASS.
        (cwd / "WORKFLOW.md").write_text(
            "**Task:** t\n**Slug:** okslug\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → ok\n- [x] 2. **CODE** → ok\n- [x] 3. **TEST** → ok\n"
            "- [x] 4. **DOCS** → ok\n- [ ] 5. **COMMIT** → x\n\n"
            "## Heartbeat\n- STAGE: DOCS\n- STARTED: 2026-05-31T10:00\n\n"
            "## Test log\nl1\nl2\nl3\nl4\nl5\nl6\n\n"
            "## Docs updated\n- 10-Developer-Docs/08-API-Reference.md\n\n"
            "## Activity log\n- STAGE PLAN STARTED\n- STAGE CODE STARTED\n"
            "- STAGE TEST STARTED\n- STAGE DOCS STARTED\n## Decisions log\n",
            encoding="utf-8",
        )
        run_case("HARD: heartbeat all-traces + artifacts → passes", 0,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m hard-ok"}})

        # 20. HARD end-to-end (Phase B): same, but CODE[x] has NO trace (no "STAGE CODE STARTED") →
        #     BLOCK (exit 2). This is the "you cannot put a bare checkbox" guarantee.
        (cwd / "WORKFLOW.md").write_text(
            "**Task:** t\n**Slug:** okslug\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → ok\n- [x] 2. **CODE** → ok\n- [x] 3. **TEST** → ok\n"
            "- [x] 4. **DOCS** → ok\n- [ ] 5. **COMMIT** → x\n\n"
            "## Heartbeat\n- STAGE: DOCS\n- STARTED: 2026-05-31T10:00\n\n"
            "## Test log\nl1\nl2\nl3\nl4\nl5\nl6\n\n"
            "## Docs updated\n- 10-Developer-Docs/08-API-Reference.md\n\n"
            "## Activity log\n- STAGE PLAN STARTED\n"
            "- STAGE TEST STARTED\n- STAGE DOCS STARTED\n## Decisions log\n",
            encoding="utf-8",
        )
        run_case("HARD: heartbeat CODE[x] without trace → blocks", 2,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m hard-block"}})

        # 21. HARD: legacy workflow (no ## Heartbeat) with [x] without a trace → NOT blocked (backward compat).
        (cwd / "WORKFLOW.md").write_text(
            "**Task:** t\n**Slug:** okslug\n**Type:** MEDIUM\n\n"
            "- [x] 1. **PLAN** → ok\n- [x] 2. **CODE** → ok\n- [x] 3. **TEST** → ok\n"
            "- [x] 4. **DOCS** → ok\n- [ ] 5. **COMMIT** → x\n\n"
            "## Test log\nl1\nl2\nl3\nl4\nl5\nl6\n\n"
            "## Docs updated\n- 10-Developer-Docs/08-API-Reference.md\n\n"
            "## Activity log\n## Decisions log\n",
            encoding="utf-8",
        )
        run_case("HARD: legacy (no heartbeat) [x] without trace → passes", 0,
                 {"cwd": str(cwd), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m legacy"}})

        # restore
        verify_docs = original_verify_docs

        # 22. PROJECT_PATH override: the hook resolves the project root from PROJECT_PATH,
        #     NOT from the payload cwd. proj2 has an all-open WORKFLOW.md (would block);
        #     the payload cwd points to a dir with NO WORKFLOW.md (would pass). If the override
        #     is honored, the commit is BLOCKED (exit 2) — proving PROJECT_PATH wins over cwd.
        proj2 = Path(tempfile.mkdtemp(prefix="kronos_proj2_"))
        nowf = Path(tempfile.mkdtemp(prefix="kronos_nowf_"))
        subprocess.run(["git", "init", "-q"], cwd=proj2, check=True)
        (proj2 / "WORKFLOW.md").write_text(
            "**Task:** real task\n**Slug:** pp-slug\n**Type:** MEDIUM\n\n"
            "- [ ] 1. **PLAN** → x\n- [ ] 2. **CODE** → x\n- [ ] 3. **TEST** → x\n"
            "- [ ] 4. **DOCS** → x\n- [ ] 5. **COMMIT** → x\n\n"
            "## Test log\n## Docs updated\n## Activity log\n## Decisions log\n",
            encoding="utf-8",
        )
        run_case("PROJECT_PATH overrides cwd → verifies that project → blocks", 2,
                 {"cwd": str(nowf), "tool_name": "Bash",
                  "tool_input": {"command": "git commit -m pp"}},
                 env_extra={"PROJECT_PATH": str(proj2)})
        shutil.rmtree(proj2, ignore_errors=True)
        shutil.rmtree(nowf, ignore_errors=True)

        print(f"\n=== Self-test results: {passed} passed, {failed} failed ===")
        return 0 if failed == 0 else 1
    finally:
        for _k, _v in _saved_env.items():
            if _v is not None:
                os.environ[_k] = _v
        shutil.rmtree(tmpdir, ignore_errors=True)
        shutil.rmtree(vault_dir, ignore_errors=True)


# ──────────────────── Entry ────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        sys.exit(self_test())

    try:
        payload = json.loads(sys.stdin.read())
    except Exception as e:
        print(f"[kronos] hook stdin not JSON: {e}", file=sys.stderr)
        sys.exit(0)
    sys.exit(run_hook(payload))
