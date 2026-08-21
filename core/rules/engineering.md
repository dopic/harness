---
rule: engineering
applies-to: [engineer, test-engineer, orchestrator]
---

# Engineering rules

- **Small tasks.** Decompose the item into tasks of at most a few hours each, posted as
  a checklist on the work item itself (visible upstream). A task that can't be described
  in one sentence is two tasks.
- **Tests before code.** BDD specs (from the item's Gherkin) come from the test-engineer
  and must be failing before implementation starts. Where BDD doesn't apply (no business
  rule: utils, adapters, infra glue), classic TDD — red, green, refactor — owned by the
  engineer.
- **Conventional Commits.** `type(scope): subject`, imperative, small. One logical change
  per commit. The work item ID goes in the commit trailer, in the provider's reference
  syntax (`AB#123` on Azure DevOps, `#123` on GitHub/GitLab — see `provider.md`). On
  GitHub, never use a closing keyword (`Closes`/`Fixes`/`Resolves`): it moves the gate
  behind the orchestrator's back. `Refs #123` links without closing.
- **No toggle without a type and a death plan.** Every feature toggle follows
  `rules/toggles.md`. Implementing a toggle not declared on the item = scope not approved.
- **No TODO without an item.** A TODO in code carries the work item ID of the debt it
  represents, or it doesn't get committed.
- **Stay in your lane.** Infra/pipeline work found mid-task goes back to the orchestrator
  for secdevops. Architecture deviation found mid-task stops work and comments the item.
- **The item is the contract.** If the item lacks the context to proceed, comment asking
  for it and stop. Do not invent requirements.
