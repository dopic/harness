#!/usr/bin/env bash
# Stop hook (OPT-IN via harness.yaml -> hooks.stop_test_gate) — blocks the session from
# finishing while fast tests fail on an uncommitted working tree. Trade-off: runs
# commands.test_fast at the end of EVERY response when the tree is dirty.
input=$(cat)
# loop guard: if we already blocked once and Claude is continuing, let it stop.
printf '%s' "$input" | grep -q '"stop_hook_active": *true' && exit 0

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
[ -z "$(git status --porcelain 2>/dev/null)" ] && exit 0

cmd=$(sed -n 's/^ *test_fast: *"\(.*\)"$/\1/p' harness.yaml | head -1)
[ -z "$cmd" ] && exit 0
case "$cmd" in *TODO*) exit 0;; esac   # placeholder from `harness init` — not configured yet

log=$(mktemp)
if ! ( eval "$cmd" ) >"$log" 2>&1; then
  {
    echo "harness stop gate: fast tests are FAILING and the working tree has uncommitted changes."
    echo "Fix the tests (or explicitly report the red state on the work item) before finishing. Last output:"
    tail -20 "$log"
  } >&2
  exit 2
fi
exit 0
