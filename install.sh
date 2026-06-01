#!/usr/bin/env bash
# KRONOS Workflow Engine — installer.
# Copies hooks/ and skills/ into ~/.claude/ and prints the settings.json
# snippet you need to register the PreToolUse hook.
#
# Usage:
#   ./install.sh            # install into ~/.claude
#   CLAUDE_DIR=/x ./install.sh   # custom target

set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"

echo "KRONOS Workflow Engine — installer"
echo "  source: $SRC"
echo "  target: $CLAUDE_DIR"
echo ""

mkdir -p "$CLAUDE_DIR/hooks"
mkdir -p "$CLAUDE_DIR/skills"

# 1. hooks
cp "$SRC/hooks/check-workflow.py" "$CLAUDE_DIR/hooks/check-workflow.py"
cp "$SRC/hooks/check-workflow.sh" "$CLAUDE_DIR/hooks/check-workflow.sh"
chmod +x "$CLAUDE_DIR/hooks/check-workflow.sh"
echo "[ok] hooks → $CLAUDE_DIR/hooks/"

# 2. skills
for d in "$SRC"/skills/kronos-*; do
    [ -d "$d" ] || continue
    name="$(basename "$d")"
    mkdir -p "$CLAUDE_DIR/skills/$name"
    cp "$d/SKILL.md" "$CLAUDE_DIR/skills/$name/SKILL.md"
    echo "[ok] skill → $name"
done

# 3. engine docs (reference copies)
cp "$SRC/KRONOS.md" "$CLAUDE_DIR/KRONOS.md"
echo "[ok] KRONOS.md → $CLAUDE_DIR/"

# 4. config → export env (optional, if config.yaml exists)
if [ -f "$SRC/config.yaml" ]; then
    echo ""
    echo "[ok] found config.yaml — values to export in your shell profile:"
    grep -E '^[A-Z_]+:' "$SRC/config.yaml" | while IFS=: read -r key val; do
        val="$(echo "$val" | sed 's/^ *//; s/^"//; s/"$//')"
        [ -n "$val" ] && echo "  export $key=\"$val\""
    done
else
    echo ""
    echo "[!] no config.yaml — copy config.example.yaml → config.yaml and fill it,"
    echo "    then export PROJECT_PATH / VAULT_PATH in your shell profile."
fi

# 5. WORKFLOW template helper
echo ""
echo "Next steps:"
echo "  1. In your project root, copy the template:"
echo "       cp \"$SRC/WORKFLOW.template.md\" /path/to/project/WORKFLOW.md"
echo "     (or let /kronos-start create it)."
echo ""
echo "  2. Register the hook in $CLAUDE_DIR/settings.json under hooks.PreToolUse"
echo "     for the Bash and PowerShell tools. Snippet:"
echo ""
cat <<'JSON'
  {
    "hooks": {
      "PreToolUse": [
        {
          "matcher": "Bash|PowerShell",
          "hooks": [
            {
              "type": "command",
              "command": "bash ~/.claude/hooks/check-workflow.sh"
            }
          ]
        }
      ]
    }
  }
JSON
echo ""
echo "  3. Run the self-test to confirm the hook works:"
echo "       python ~/.claude/hooks/check-workflow.py --self-test"
echo ""
echo "Done."
