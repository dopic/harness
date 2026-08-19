---
name: development-cycle
description: The orchestrated flow from demand to done. The orchestrator enforces it; every agent references its own step.
---

# Development cycle

```
demand
  → issue-writer                 creates items, gate = harness:proposed, STOPS
  → HUMAN GATE                   Douglas approves upstream → harness:approved
  → orchestrator                 pulls approved items, routes
      → software-architect       if item tagged arch-review, or change touches a module
                                 boundary / public contract
      → solutions-architect      if item has a cloud/infra component
  → test-engineer                failing BDD specs from the item's Gherkin scenarios
  → engineer-{stack}             small tasks; make specs pass; unit-level TDD
  → PR                           code-reviewer ∥ security-reviewer (parallel, comment-only)
  → merge                        after both approve (branch protection may also require human)
  → qa                           BUILDS integration / acceptance (Cypress) / smoke suites
  → secdevops                    wires each suite into its declared pipeline stage
  → pipeline VALIDATES           green = evidence
  → harness:done                 closing comment on the item: what shipped, links
```

## Orchestrator invariants

1. Only items in `harness:approved` are picked up. Never `proposed`, never unlabeled.
2. One item at a time per repo. No parallel items touching the same code.
3. Every gate transition is written upstream immediately. State never lives only in
   the session.
4. Tests exist and fail before implementation starts. No exceptions without a comment
   on the item explaining why (e.g., pure-infra task).
5. An item does not close while: any review thread is open, any declared test suite
   lacks a pipeline stage, or the pipeline is red.
6. Two review rounds without convergence → comment mentioning Douglas; stop.
7. Any blocker becomes a comment on the item mentioning Douglas. Never fail silently.
8. Rejection path: Douglas comments + tags `harness:needs-revision` → issue-writer
   re-reads the comment and rewrites; back to `harness:proposed`.
