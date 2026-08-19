#!/usr/bin/env bash
# SessionStart hook — injects harness context and warns about core drift.
# stdout becomes session context. Never blocks; no external dependencies.
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
[ -f .harness/manifest.json ] || exit 0

mv=$(sed -n 's/.*"core_version": *"\([^"]*\)".*/\1/p' .harness/manifest.json | head -1)
cp=$(sed -n 's/^ *core_path: *"\(.*\)".*/\1/p' harness.yaml 2>/dev/null | head -1)
if [ -n "$cp" ] && [ -f "$cp/core/VERSION" ]; then
  cv=$(tr -d '[:space:]' < "$cp/core/VERSION")
  if [ -n "$mv" ] && [ "$mv" != "$cv" ]; then
    echo "harness WARNING: compiled artifacts are core v$mv but the core checkout is v$cv — run 'harness update' before trusting agents/rules."
  fi
fi

echo "harness: this repo is harness-managed. Gate: harness:proposed -> approved -> in-dev -> in-review -> done; only the human moves proposed->approved. Compiled files (.claude/harness/**, .claude/agents/**, .claude/commands/**, CLAUDE.md) are write-protected by hook."
exit 0
