#!/usr/bin/env bash
# PreToolUse hook (Edit|Write|MultiEdit) — deterministic guards:
# 1. Block hand-edits to compiled harness artifacts (edit the core, run `harness update`).
# 2. Block raw .drawio files (diagram convention: .drawio.svg only).
input=$(cat)
fp=$(printf '%s' "$input" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)
[ -z "$fp" ] && exit 0
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"

case "$fp" in
  "$root/.claude/harness/"*|"$root/.claude/agents/"*|"$root/.claude/commands/"*|"$root/CLAUDE.md"|.claude/harness/*|.claude/agents/*|.claude/commands/*|CLAUDE.md)
    echo "harness: blocked — this is a compiled artifact. Edit the harness core and run 'harness update'. Repo-local rules belong in .harness/overrides/rules/." >&2
    exit 2;;
esac

case "$fp" in
  *.drawio)
    echo "harness: blocked — raw .drawio is forbidden in repos (opaque XML in review). Save as .drawio.svg (File > Export as > SVG, 'Include a copy of my diagram' checked). See templates/architecture/diagram-conventions.md." >&2
    exit 2;;
esac
exit 0
