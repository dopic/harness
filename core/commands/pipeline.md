---
name: pipeline
agent: secdevops
description: Create or update CI/CD, hooks, policies, and the test-suite stages.
argument-hint: "[what changed — or empty for a full check]"
---
Act as the **secdevops** agent (see `agents/secdevops.md`). Scope: $ARGUMENTS.
Ensure the baseline (lefthook, CI with lint/fast tests/SAST/dep scan/secret scan,
branch protection) and materialize every `harness.yaml → test-suites` entry as a real
pipeline stage (template: `templates/pipelines/`). Ship changes as a PR through the
normal review flow.
