---
name: dev
agent: orchestrator
description: Run the full development cycle for one approved item.
argument-hint: "[item id — omit to take the next approved]"
---
Act as the **orchestrator** (see `agents/orchestrator.md`) and run
`workflows/development-cycle.md` for item: $ARGUMENTS (or the next `harness:approved`
item if none given).

Dispatch each phase to the corresponding subagent (architects if flagged →
test-engineer → engineer-{stack} → code-reviewer ∥ security-reviewer → qa →
secdevops). Enforce every invariant; mirror every gate transition upstream; stop and
comment mentioning Douglas on any blocker. Never pick an item that is not
`harness:approved`.
