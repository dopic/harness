# Diagram conventions

## Placement (reach decides)

- Crosses this repo → client's global knowledge repo (`architecture.global_docs`),
  using Confluence's native draw.io integration; the page links back to the repo when
  the diagram was born there.
- Repo-scope → `docs/architecture/diagrams/`.

## Format

- Canonical repo format: **`.drawio.svg`** — one file, editable in draw.io, rendered
  natively in PRs and browsers. Raw `.drawio` is forbidden in repos (opaque XML in
  review).
- One diagram per file.
- Mermaid allowed only repo-scope, C4 Component level and below, where textual diff
  beats aesthetics.

## Naming

- C4 (software-architect): `c4-<level>-<scope>.drawio.svg`
  (e.g. `c4-container-payments.drawio.svg`).
- Solution (solutions-architect): `solution-<scope>.drawio.svg`, drawn with the
  official icon library of the cloud in use (`architecture.cloud`): AWS Architecture
  Icons / Azure architecture icons / Google Cloud icons — all native draw.io libraries.

## Hygiene

Every diagram carries a title block: owner, date, review-by. A diagram nobody has
re-read past its review date is flagged by `harness doctor`.
