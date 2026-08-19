---
rule: bdd
applies-to: [issue-writer, test-engineer, engineer, qa]
---

# BDD rules

- **The item's Gherkin is the source.** Acceptance criteria on user stories are written
  as `Given / When / Then` scenarios. Each scenario becomes exactly one executable spec.
- **Scenario without a spec = incomplete item.** The test-engineer's deliverable is the
  full scenario→spec map, commented on the item.
- **Spec without a scenario = unapproved scope.** If a needed test has no scenario, the
  scenario is missing from the item: comment upstream, get it added (through the gate if
  it changes scope), then write the spec.
- **Scenarios are behavior, not UI scripts.** "When the customer submits an expired
  card", not "When the user clicks #submit-btn". UI mechanics belong to QA's acceptance
  layer, not to the story.
- **Framework per stack** comes from `harness.yaml` (`bdd_frameworks`): cucumber-js /
  vitest-gherkin (JavaScript), Reqnroll (C#), pytest-bdd (Python).
- **When BDD doesn't fit** (no observable business behavior), say so explicitly on the
  item and fall back to TDD. Silence is not a decision.
