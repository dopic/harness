# harness

An agent-based development harness. Tool-agnostic core, compiled per target tool.
Current compile target: **Claude Code**. Validated providers: **Azure DevOps**, **GitHub**.

## Principles

- **One owner per definition.** Everything lives in `core/` as plain Markdown + YAML
  frontmatter, with no tool-specific syntax. The installer *compiles* the core into the
  target tool's format. Never edit compiled artifacts — edit the core and run
  `harness update`.
- **The work item is the context contract.** An approved item must contain everything an
  agent needs to develop it without access to the conversation that created it.
- **State lives upstream.** Gate transitions (`harness:proposed` → `harness:approved` →
  `harness:in-dev` → `harness:in-review` → `harness:done`) are labels/tags on the
  provider, never session-only state.
- **Tests before code.** BDD by default (Gherkin scenarios from the item become failing
  executable specs before implementation); TDD where BDD doesn't apply.
- **A test the pipeline doesn't run does not exist.** Every suite is declared in the
  `test-suites` section of `harness.yaml` and wired to a pipeline stage.

## Layout

```
core/           agents, rules, templates, stacks, workflows  (single source of truth)
providers/      neutral verb interface + adapters (azure-devops first; github/gitlab stubs)
schema/         commented harness.yaml example (per-repo config)
installer/      harness CLI: init · install · update · doctor
docs/           project docs, including the original plan (pt-BR)
```

## Install into a project repo

One-time setup (the `harness` command becomes global; the core stays in this checkout
and is read at runtime):

```bash
pipx install ~/git/harness/installer                    # or: pip install …
echo 'export HARNESS_HOME="$HOME/git/harness"' >> ~/.zshrc   # how the CLI finds core/
```

Then, from inside any project repo:

```bash
harness init --provider github      # writes harness.yaml (records core_path), docs skeleton
harness provider-setup              # GitHub/GitLab only: creates the harness:*, type:* and
                                    # routing labels upstream (idempotent; --dry-run to preview)
harness install --tool claude-code  # compiles core → CLAUDE.md, .claude/…, lefthook.yml
harness doctor                      # config, provider auth, labels, drift checks
```

`init` defaults to `--provider azure-devops`; `provider-setup` is a no-op there (work
item types and tags are native fields). On GitHub it is **not** optional — `gh issue
create --label` fails on a label that does not exist yet, so nothing works before it.

Core resolution order: `--core` flag → `$HARNESS_HOME` → `core_path` in `harness.yaml`
→ script location (checkout runs only). Without `HARNESS_HOME`, pass
`--core ~/git/harness` on the first `init`; after that it's recorded in the repo.

Updating: changes to **core/** need nothing (read live) — just `harness update` in each
repo to recompile. Changes to **installer/harness_cli.py** need `pipx reinstall harness-cli`.

Per-repo customization goes in `.harness/overrides/` (rules appended after core rules;
overrides win). `harness update` recompiles from the current core without touching
`harness.yaml` or overrides.

## The flow

```
demand → issue-writer → items tagged harness:proposed
       → [HUMAN GATE: approve upstream → harness:approved]
       → orchestrator → (architects if flagged) → test-engineer (failing BDD specs)
       → engineer-{stack} (make specs pass; unit TDD)
       → PR → code-reviewer ∥ security-reviewer (comment upstream, never edit)
       → merge → qa builds suites → pipeline validates them (secdevops wires stages)
       → harness:done
```

## Enforcement layers

Three layers, weakest to strongest: **rules** (prose the agents follow), **git hooks**
(lefthook — lint/format/secret-scan at commit, fast tests at push; applies to humans
and agents alike), and **Claude Code hooks** (shell guards the agent cannot skip,
compiled into `.claude/settings.json`, toggled in `harness.yaml → hooks`):

- `protect_compiled` (PreToolUse) — blocks hand-edits to compiled artifacts
  (`.claude/harness/**`, `.claude/agents/**`, `.claude/commands/**`, `CLAUDE.md`) and
  raw `.drawio` files. On by default.
- `session_context` (SessionStart) — injects the gate reminder and warns when compiled
  artifacts are behind the core checkout. On by default.
- `stop_test_gate` (Stop) — refuses to let a session finish while `commands.test_fast`
  fails on a dirty working tree. **Opt-in**: it runs the tests at the end of every
  response, so enable it only where `test_fast` is genuinely fast.

## Roadmap

- Cursor compiler (`AGENTS.md` + `.cursor/rules`) and generic `agents-md` target.
- GitLab adapter validated end to end (recipes stubbed in `providers/gitlab.md`).
- Optional reviewer identity on GitHub (a machine account token) so `gh pr review
  --approve` can replace the `[harness:approved-by:*]` marker comments.
- Two-way GitHub Projects v2 sync for `provider.project` (today items are only *added*
  to the board; gate state is never mirrored into a board column).
- Stale-item notifications (items sitting in `harness:proposed`).

## Versioning

`core/VERSION` is bumped on any core change. `harness doctor` reports repos whose
compiled artifacts are behind the installed core. No silent auto-update.

## License

Copyright (C) 2026 Douglas Picolotto

This program is free software: you can redistribute it and/or modify it under the
terms of the GNU Affero General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the license along with this program in
[`LICENSE`](LICENSE). If not, see <https://www.gnu.org/licenses/>.
