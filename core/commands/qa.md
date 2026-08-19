---
name: qa
agent: qa
description: Build or update the expensive test suites (integration / acceptance / smoke).
argument-hint: "<scope — feature, flow or suite name>"
---
Act as the **qa** agent (see `agents/qa.md`) for scope: $ARGUMENTS.
Build the suites, update `harness.yaml → test-suites` for anything new or changed, and
hand the stage wiring to secdevops (or flag it on the item). Remember: a suite the
pipeline doesn't run does not exist.
