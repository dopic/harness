---
rule: toggles
applies-to: [issue-writer, engineer, code-reviewer]
---

# Feature toggle rules

Taxonomy (Hodgson/Fowler). The issue-writer decides IF a toggle is needed and its type;
the engineer implements it as declared; reviewers block undeclared toggles.

| Type | Purpose | Lifespan | Born with |
|---|---|---|---|
| Release | hide incomplete work on main | days–weeks | a linked removal item WITH a target date |
| Experiment | A/B, measure | weeks | a linked removal item + the metric that decides |
| Ops | kill switch, load shedding | long-lived | an owner + periodic review date |
| Permission | per-plan/per-role capability | long-lived | an owner + periodic review date |

- **A toggle without a death plan is debt with interest.** Release/Experiment toggles
  ship together with their removal item. The removal item is not optional paperwork —
  it goes through the same gate.
- **Registry:** every toggle is recorded (template `templates/toggles/feature-toggle.md`)
  in the file configured at `harness.yaml → toggles.registry`: name, type, owner,
  created, expiry/review, removal item link.
- **Toggle checks live at the edge**, not scattered through domain logic. One decision
  point per toggle wherever feasible.
- **Expired toggle = red doctor.** `harness doctor` flags registry entries past their
  expiry/review date.
