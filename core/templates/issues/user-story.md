# User Story

**Title:** <verb-first, outcome-focused>
**As a** <role> **I want** <capability> **so that** <business value>.

## Context

<Why now. Links: ADRs touched, global docs, prior items. Enough for an agent with no
conversation history to understand the tension. 2–5 sentences.>

## Acceptance criteria (Gherkin — each scenario becomes one executable spec)

```gherkin
Scenario: <behavior, not UI mechanics>
  Given <initial state>
  When <action>
  Then <observable outcome>
```

<Repeat per scenario. Edge cases and error paths are scenarios too.>

## Feature toggle

- Needed: yes/no. If yes — Type: Release | Experiment | Ops | Permission ·
  Name: `<toggle-name>` · Removal item: <link> (Release/Experiment) · Owner + review
  date (Ops/Permission).

## Routing flags

- [ ] `arch-review` (module boundary / public contract / ADR impact)
- [ ] `security-review` (auth, personal data, money, new external input)

## Out of scope

<Explicitly. What a reasonable engineer might assume is included, but isn't.>

## Open questions

<Unknowns as questions with an owner — or a linked Spike. Never invented answers.>
