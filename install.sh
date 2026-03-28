#!/usr/bin/env bash
# AutoDoc installer — sets up autodoc in any Claude Code project
# Usage: bash install.sh [target-directory]
# Example: bash install.sh ~/my-project

set -e

AUTODOC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-$(pwd)}"

echo ""
echo "  AutoDoc installer"
echo "  ================="
echo "  Source : $AUTODOC_DIR"
echo "  Target : $TARGET"
echo ""

# Verify target exists
if [ ! -d "$TARGET" ]; then
    echo "  ERROR: Target directory does not exist: $TARGET"
    exit 1
fi

# Create directories
mkdir -p "$TARGET/.claude/commands"
mkdir -p "$TARGET/Claude_Scripts"
mkdir -p "$TARGET/docs"

# Copy scripts
cp "$AUTODOC_DIR/Claude_Scripts/log_activity.py"  "$TARGET/Claude_Scripts/log_activity.py"
cp "$AUTODOC_DIR/Claude_Scripts/daily_summary.py" "$TARGET/Claude_Scripts/daily_summary.py"
cp "$AUTODOC_DIR/.claude/commands/summary.md"     "$TARGET/.claude/commands/summary.md"

# Copy config only if it doesn't exist yet (preserve user config)
if [ ! -f "$TARGET/Claude_Scripts/autodoc.config.json" ]; then
    cp "$AUTODOC_DIR/Claude_Scripts/autodoc.config.json" "$TARGET/Claude_Scripts/autodoc.config.json"
    echo "  Created : Claude_Scripts/autodoc.config.json"
else
    echo "  Skipped : Claude_Scripts/autodoc.config.json already exists (not overwritten)"
fi

# Merge hook into .claude/settings.local.json
SETTINGS="$TARGET/.claude/settings.local.json"

HOOK_ENTRY='{"type":"command","command":"python Claude_Scripts/log_activity.py","timeout":15}'

if [ ! -f "$SETTINGS" ]; then
    cat > "$SETTINGS" <<EOF
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          $HOOK_ENTRY
        ]
      }
    ]
  }
}
EOF
    echo "  Created : .claude/settings.local.json"
else
    # Check if hook is already present
    if grep -q "log_activity.py" "$SETTINGS"; then
        echo "  Skipped : hook already present in settings.local.json"
    else
        echo ""
        echo "  WARNING: .claude/settings.local.json already exists."
        echo "  Please add the following hook manually under hooks > Stop:"
        echo ""
        echo "    $HOOK_ENTRY"
        echo ""
    fi
fi

echo ""
echo "  Done! AutoDoc is ready in: $TARGET"
echo ""
echo "  Next steps:"
echo "    1. Open the project in Claude Code"
echo "    2. Edit Claude_Scripts/autodoc.config.json to set your language (\"es\" or \"en\")"
echo "    3. Start coding — entries appear in docs/YYYY-MM-DD.md automatically"
echo "    4. Type /summary at any time to generate the day summary"
echo ""
