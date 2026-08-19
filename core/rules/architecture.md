---
rule: architecture
applies-to: [software-architect, solutions-architect, code-reviewer, issue-writer]
---

# Architecture rules

- **The Haiku's quality-attribute ranking is the tiebreaker.** When two decisions
  conflict, the higher-ranked attribute wins. No Haiku for the system yet = write it
  first (template: `templates/architecture/architecture-haiku.md`).
- **A decision produces an ADR** (Nygard format: Context · Decision · Consequences —
  template: `templates/architecture/adr.md`). ADRs are immutable once accepted; a change
  of direction is a NEW ADR that supersedes the old one. Disagreement is a proposed ADR,
  never a chat-agreed exception.
- **Placement rule (ADRs and diagrams alike):** decision/diagram whose scope crosses
  this repo → the client's global knowledge repo (`architecture.global_docs`);
  repo-scope → `docs/architecture/adrs/` and `docs/architecture/diagrams/`.
  The criterion is reach, not the author's preference: if another repo must know it,
  it's global.
- **Accepted deviation = ADR with a risk-acceptance block:** owner, scope, valid-until,
  compensating control, re-read date.
- **Diagrams:** C4 (Context, Container, Component; Code only when it pays for itself).
  Canonical repo format `.drawio.svg` — one diagram per file, named
  `c4-<level>-<scope>.drawio.svg`. Raw `.drawio` is forbidden in repos (opaque XML in
  review). Mermaid allowed repo-scope at Component level and below. In Confluence,
  diagrams use the native draw.io integration, linking back to the repo when born there.
- **Implementation that contradicts an accepted ADR is a review blocker.** The exit is
  a superseding ADR, not a merge.
