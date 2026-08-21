#!/usr/bin/env python3
"""harness CLI — init | install | update | doctor.

Compiles the tool-agnostic core/ into a target tool's format (currently: claude-code).
The core is the single source of truth; compiled artifacts are build output and are
never edited by hand.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

__version__ = "0.7.1"          # kept in lockstep with core/VERSION

MANIFEST = ".harness/manifest.json"
CONFIG = "harness.yaml"
GATE_TAGS = [
    "harness:proposed", "harness:approved", "harness:in-dev",
    "harness:in-review", "harness:done", "harness:needs-revision",
]
# Item types and routing flags are native fields on Azure DevOps but plain labels on
# GitHub/GitLab, so they have to be bootstrapped there before any item can be created.
TYPE_LABELS = ["type:user-story", "type:bug", "type:tech-debt", "type:spike"]
ROUTING_LABELS = ["arch-review", "security-review"]
LABEL_STYLE = {
    "harness:proposed":       ("D4C5F9", "Harness gate: written, awaiting human approval"),
    "harness:approved":       ("0E8A16", "Harness gate: approved — the orchestrator may pick it up"),
    "harness:in-dev":         ("1D76DB", "Harness gate: specs and implementation in progress"),
    "harness:in-review":      ("FBCA04", "Harness gate: PR open, under review"),
    "harness:done":           ("6E7681", "Harness gate: delivered, pipeline green"),
    "harness:needs-revision": ("B60205", "Harness gate: rejected — issue-writer rewrites it"),
    "type:user-story":        ("0052CC", "Harness item type: user story"),
    "type:bug":               ("D73A4A", "Harness item type: bug"),
    "type:tech-debt":         ("BFD4F2", "Harness item type: tech debt"),
    "type:spike":             ("C2E0C6", "Harness item type: spike"),
    "arch-review":            ("E99695", "Routing flag: software-architect reviews before dev"),
    "security-review":        ("F9D0C4", "Routing flag: security-reviewer does a design pass"),
}
# Providers whose vocabulary lives in labels that must exist before first use.
LABEL_BASED_PROVIDERS = {"github", "gitlab"}
PROVIDER_INIT_DEFAULTS = {
    "azure-devops": ("https://dev.azure.com/YOUR_ORG", "YourProject"),
    "github":       ("YOUR_GITHUB_OWNER", ""),
    "gitlab":       ("YOUR_GITLAB_GROUP", ""),
}
PIPELINE_TEMPLATE = {
    "azure-devops": "azure-pipelines.yml",
    "github": "github-actions.yml",
}


def expected_labels(cfg: dict) -> list[str]:
    gates = cfg.get("provider", {}).get("gate_tags") or GATE_TAGS
    return list(gates) + TYPE_LABELS + ROUTING_LABELS


def repo_slug(cfg: dict) -> str:
    prov = cfg.get("provider", {})
    owner = str(prov.get("organization", "")).rstrip("/").split("/")[-1]
    return f"{owner}/{prov.get('repository', '')}"


# ---------------------------------------------------------------- helpers

def fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def last_line(text: str) -> str:
    """Last non-empty line of a CLI's output — the part that says what went wrong."""
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return lines[-1].strip() if lines else ""


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)


def locate_core(explicit: str | None, cfg: dict | None) -> Path | None:
    """core/ location: --core > $HARNESS_HOME > harness.yaml > this file's repo."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    if os.environ.get("HARNESS_HOME"):
        candidates.append(Path(os.environ["HARNESS_HOME"]).expanduser())
    if cfg and cfg.get("harness", {}).get("core_path"):
        candidates.append(Path(cfg["harness"]["core_path"]).expanduser())
    candidates.append(Path(__file__).resolve().parent.parent)  # repo checkout layout
    for c in candidates:
        root = c if (c / "core").is_dir() else (c.parent if (c.parent / "core").is_dir() else None)
        if root:
            return root
    return None


def find_core(explicit: str | None, cfg: dict | None) -> Path:
    root = locate_core(explicit, cfg)
    if root is None:
        fail("cannot locate the harness repo (core/). Use --core or set HARNESS_HOME.")
    assert root is not None   # fail() exited; this only narrows the type
    return root


def load_config(repo: Path) -> dict:
    p = repo / CONFIG
    if not p.exists():
        fail(f"{CONFIG} not found in {repo}. Run `harness init` first.")
    try:
        return yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as e:
        fail(f"{CONFIG} is not valid YAML: {e}")
    raise AssertionError


class VersionAction(argparse.Action):
    """argparse's built-in version action reflows the text; this keeps the layout."""

    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(version_banner())
        parser.exit()


def version_banner() -> str:
    try:
        root = locate_core(None, None)
        if root is None:
            return (f"harness-cli {__version__}\n"
                    "core        not found — set HARNESS_HOME or pass --core")
        cv = core_version(root)
        drift = "" if cv == __version__ else \
            "  << drift: versions are locked; run `pipx reinstall harness-cli`"
        return f"harness-cli {__version__}\ncore        {cv}  ({root}){drift}"
    except OSError as e:
        return f"harness-cli {__version__}\ncore        unreadable ({e})"


def core_version(harness_root: Path) -> str:
    return (harness_root / "core" / "VERSION").read_text().strip()


# ---------------------------------------------------------------- stack commands

COMMAND_KEYS = ["lint", "format", "test_fast", "build"]

# Last-resort defaults: what a stack's toolchain does when the repo says nothing.
# `init` prefers whatever the detectors below read off the repo; these only fill gaps,
# so an unconfigured key fails loudly instead of passing as a green `echo TODO`.
STACK_COMMANDS = {
    "javascript": {"lint": "yarn lint", "format": "yarn format",
                   "test_fast": "yarn test", "build": "yarn build"},
    "csharp":     {"lint": "dotnet format --verify-no-changes", "format": "dotnet format",
                   "test_fast": "dotnet test", "build": "dotnet build -c Release"},
    "python":     {"lint": "ruff check .", "format": "ruff format .",
                   "test_fast": "pytest -q", "build": "python -m build"},
    "rust":       {"lint": "cargo clippy --all-targets -- -D warnings",
                   "format": "cargo fmt --all",
                   "test_fast": "cargo test", "build": "cargo build --locked"},
}
# The committed lockfile picks the package manager — never the other way round.
JS_RUNNERS = [("bun.lockb", "bun run"), ("bun.lock", "bun run"),
              ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
              ("package-lock.json", "npm run")]
# First script that exists wins; the head of each list is the fallback name, so a repo
# with no `lint` script gets `yarn lint` (fails at the hook) rather than a silent pass.
JS_SCRIPTS = {"lint": ["lint", "lint:check", "eslint"],
              "format": ["format", "fmt", "prettier"],
              "test_fast": ["test:unit", "test"],
              "build": ["build", "compile"]}


def detect_javascript(repo: Path) -> dict[str, str]:
    runner = next((r for f, r in JS_RUNNERS if (repo / f).exists()), "yarn")
    scripts: dict = {}
    pkg = repo / "package.json"
    if pkg.exists():
        try:
            scripts = (json.loads(pkg.read_text()) or {}).get("scripts") or {}
        except (json.JSONDecodeError, OSError):
            scripts = {}
    return {key: f"{runner} {next((n for n in names if n in scripts), names[0])}"
            for key, names in JS_SCRIPTS.items()}


def detect_rust(repo: Path) -> dict[str, str]:
    cargo = repo / "Cargo.toml"
    if not cargo.exists():
        return {}
    ws = ["--workspace"] if "[workspace]" in cargo.read_text() else []
    j = lambda *parts: " ".join(["cargo", parts[0], *ws, *parts[1:]])   # noqa: E731
    return {"lint": j("clippy", "--all-targets", "--", "-D", "warnings"),
            "format": "cargo fmt --all",
            "test_fast": j("test"),
            "build": j("build", "--locked")}


def detect_python(repo: Path) -> dict[str, str]:
    py = repo / "pyproject.toml"
    text = py.read_text() if py.exists() else ""
    # The runner has to match how deps were installed, or the tools are not on PATH.
    prefix = ("uv run " if (repo / "uv.lock").exists() else
              "poetry run " if "[tool.poetry]" in text else "")
    out = {}
    if "ruff" in text or (repo / "ruff.toml").exists() or (repo / ".ruff.toml").exists():
        out["lint"] = prefix + "ruff check ."
        out["format"] = prefix + "ruff format ."
    elif "black" in text or "flake8" in text:
        out["lint"] = prefix + "flake8 ."
        out["format"] = prefix + "black ."
    if "pytest" in text or (repo / "tests").is_dir():
        out["test_fast"] = prefix + "pytest -q"
    if "[build-system]" in text:
        out["build"] = prefix + "python -m build"
    return out


def detect_csharp(repo: Path) -> dict[str, str]:
    found = (sorted(repo.glob("*.sln")) or sorted(repo.glob("*/*.sln"))
             or sorted(repo.glob("*.csproj")) or sorted(repo.glob("*/*.csproj")))
    if not found:
        return {}
    t = " " + shlex.quote(str(found[0].relative_to(repo)))
    return {"lint": f"dotnet format{t} --verify-no-changes",
            "format": f"dotnet format{t}",
            "test_fast": f"dotnet test{t}",
            "build": f"dotnet build{t} -c Release"}


DETECTORS = {"javascript": detect_javascript, "csharp": detect_csharp,
             "python": detect_python, "rust": detect_rust}


def stack_command_set(repo: Path, stack: str, detect: bool = True) -> dict[str, str]:
    """What one stack contributes: its defaults, overridden by whatever the repo says."""
    cmds = dict(STACK_COMMANDS.get(stack, {}))
    if detect and stack in DETECTORS:
        cmds.update({k: v for k, v in DETECTORS[stack](repo).items() if v})
    return cmds


def resolve_commands(repo: Path, stacks: list[str], detect: bool = True) -> dict[str, str]:
    """One command per key for the whole repo. A multi-stack repo chains its stacks in
    declaration order with `&&` — the first stack that fails stops the chain, which is
    what lefthook and the pipeline contract expect from a single command string."""
    per_stack = [stack_command_set(repo, stack, detect) for stack in stacks]
    out = {}
    for key in COMMAND_KEYS:
        parts: list[str] = []
        for cmds in per_stack:
            c = cmds.get(key)
            if c and c not in parts:
                parts.append(c)
        out[key] = " && ".join(parts) if parts else f"echo TODO: {key}"
    return out


def render_commands(cmds: dict[str, str]) -> str:
    q = json.dumps            # YAML-safe scalar: commands carry `:`, quotes and `&&`
    return "".join(f"  {k}: {q(cmds[k])}\n" for k in COMMAND_KEYS)


# ---------------------------------------------------------------- init

INIT_TEMPLATE = """harness:
  core_version: "{version}"
  core_path: "{core_path}"

provider:
  kind: {provider}
  organization: "{org}"
  project: "{project}"
  repository: "{repo_name}"
  gate_tags: [{gates}]

stacks:
{stacks}
bdd_frameworks:
  javascript: cucumber-js
  csharp: reqnroll
  python: pytest-bdd
  rust: cucumber-rs

commands:
{commands}
security:
  asvs_level: 1
  secret_scan: gitleaks

architecture:
  global_docs: ""            # client's global knowledge repo (Confluence, ADO wiki…)
  adr_dir: docs/architecture/adrs
  diagrams_dir: docs/architecture/diagrams
  diagram_format: drawio-svg
  cloud: aws

toggles:
  system: config-file
  registry: docs/toggles.md

hooks:                       # Claude Code hooks (deterministic enforcement)
  protect_compiled: true     # block hand-edits to compiled artifacts + raw .drawio
  session_context: true      # inject gate reminder + core-drift warning at session start
  stop_test_gate: false      # OPT-IN: block finishing while fast tests fail on a dirty tree

test-suites: []              # QA adds entries: name / path / command / stage
"""


def cmd_init(args: argparse.Namespace) -> None:
    repo = Path(args.repo).resolve()
    harness_root = find_core(args.core, None)
    cfg_path = repo / CONFIG
    if cfg_path.exists() and not args.force:
        fail(f"{CONFIG} already exists in {repo} (use --force to overwrite).")
    stacks = [s.strip() for s in args.stacks.split(",")] if args.stacks else ["javascript"]
    commands = resolve_commands(repo, stacks, detect=not args.no_detect)
    def_org, def_project = PROVIDER_INIT_DEFAULTS[args.provider]
    cfg_path.write_text(INIT_TEMPLATE.format(
        version=core_version(harness_root),
        core_path=str(harness_root),
        provider=args.provider,
        org=args.organization or def_org,
        project=args.project or def_project,
        repo_name=args.repository or repo.name,
        gates=", ".join(GATE_TAGS),
        stacks="".join(f"  - {s}\n" for s in stacks),
        commands=render_commands(commands),
    ))
    for d in ["docs/architecture/adrs", "docs/architecture/diagrams",
              ".harness/overrides/rules"]:
        (repo / d).mkdir(parents=True, exist_ok=True)
    reg = repo / "docs" / "toggles.md"
    if not reg.exists():
        reg.write_text("# Feature toggle registry\n\n(see harness "
                       "core/templates/toggles/feature-toggle.md)\n")
    print(f"initialized: {cfg_path}")
    src = "stack defaults" if args.no_detect else "the repo + stack defaults"
    print(f"commands (from {src} — review them, they gate commits and CI):")
    for k in COMMAND_KEYS:
        print(f"  {k}: {commands[k]}")
    if args.provider == "github":
        print("next: edit harness.yaml (provider.organization = owner, "
              "provider.repository = repo name; provider.project is an optional "
              "Projects v2 board title), then:")
        print("      harness provider-setup            # creates the harness:* / type:* labels")
        print("      harness install --tool claude-code")
    else:
        print("next: edit harness.yaml (provider org/project, commands), "
              "then `harness install --tool claude-code`")


# ---------------------------------------------------------------- compile (claude-code)

def read_dir(d: Path) -> dict[str, str]:
    return {p.name: p.read_text() for p in sorted(d.glob("*.md"))}


def compile_claude_code(harness_root: Path, repo: Path, cfg: dict) -> list[Path]:
    core = harness_root / "core"
    out: list[Path] = []

    def write(rel: str, content: str) -> None:
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        out.append(p)

    # -- support files the agents read at runtime
    for sub in ["rules", "workflows"]:
        for name, text in read_dir(core / sub).items():
            write(f".claude/harness/{sub}/{name}", text)
    for tsub in ["issues", "architecture", "toggles"]:
        for p in sorted((core / "templates" / tsub).glob("*")):
            write(f".claude/harness/templates/{tsub}/{p.name}", p.read_text())
    # provider adapter (+ interface)
    kind = cfg.get("provider", {}).get("kind", "azure-devops")
    adapter = harness_root / "providers" / f"{kind}.md"
    if not adapter.exists():
        fail(f"unknown provider kind: {kind}")

    # only this provider's pipeline template — secdevops must not see three CI dialects
    pipelines = core / "templates" / "pipelines"
    wanted = PIPELINE_TEMPLATE.get(kind)
    chosen = [pipelines / wanted] if wanted and (pipelines / wanted).exists() else \
        sorted(pipelines.glob("*"))
    for p in chosen:
        write(f".claude/harness/templates/pipelines/{p.name}", p.read_text())
    write(".claude/harness/provider.md",
          (harness_root / "providers" / "interface.md").read_text()
          + "\n\n---\n\n" + adapter.read_text())

    # overrides appended after core rules
    ovr_dir = repo / ".harness/overrides/rules"
    overrides = sorted(ovr_dir.glob("*.md")) if ovr_dir.is_dir() else []

    def agent_preamble(meta: dict) -> str:
        rules = meta.get("rules", [])
        lines = ["", "## Harness context (compiled)", "",
                 f"- Repo config: `harness.yaml` (provider: {kind})",
                 "- Provider recipes: `.claude/harness/provider.md`",
                 "- Workflow: `.claude/harness/workflows/development-cycle.md`"]
        if rules:
            lines.append("- Read and obey these rules before acting: "
                         + ", ".join(f"`.claude/harness/rules/{r}.md`" for r in rules))
        if overrides:
            lines.append("- Repo overrides (win over core rules): "
                         + ", ".join(f"`.harness/overrides/rules/{p.name}`" for p in overrides))
        lines.append("- Templates: `.claude/harness/templates/`")
        return "\n".join(lines) + "\n"

    # -- agents
    stacks_cfg = cfg.get("stacks") or ["javascript"]
    for name, text in read_dir(core / "agents").items():
        meta, body = split_frontmatter(text)
        if meta.get("compile") == "per-stack":
            tmpl_meta, tmpl_body = meta, body
            for stack in stacks_cfg:
                sf = core / "stacks" / f"{stack}.md"
                if not sf.exists():
                    fail(f"unknown stack in harness.yaml: {stack}")
                smeta, sbody = split_frontmatter(sf.read_text())
                rendered = (tmpl_body
                            .replace("{{STACK_ID}}", smeta["stack-id"])
                            .replace("{{STACK_NAME}}", smeta["stack-name"])
                            .replace("{{STACK_BLOCK}}", sbody.strip()))
                agent_name = f"engineer-{smeta['stack-id']}"
                desc = tmpl_meta["description"].replace("{{STACK_NAME}}", smeta["stack-name"])
                fm = f"---\nname: {agent_name}\ndescription: {desc}\n---\n"
                write(f".claude/agents/{agent_name}.md",
                      fm + agent_preamble(tmpl_meta) + rendered)
        else:
            fm = f"---\nname: {meta['name']}\ndescription: {meta['description']}\n---\n"
            write(f".claude/agents/{meta['name']}.md", fm + agent_preamble(meta) + body)

    # -- commands
    for name, text in read_dir(core / "commands").items():
        meta, body = split_frontmatter(text)
        fm_lines = [f"description: {meta['description']}"]
        if meta.get("argument-hint"):
            fm_lines.append(f"argument-hint: \"{meta['argument-hint']}\"")
        write(f".claude/commands/{meta['name']}.md",
              "---\n" + "\n".join(fm_lines) + "\n---\n" + body)

    # -- Claude Code hooks (deterministic enforcement)
    hooks_cfg = cfg.get("hooks") or {}
    hooks_dir = core / "hooks"
    for p in sorted(hooks_dir.glob("*.sh")):
        write(f".claude/harness/hooks/{p.name}", p.read_text())
        (repo / f".claude/harness/hooks/{p.name}").chmod(0o755)

    settings_hooks: dict = {}
    def hook_entry(script: str, matcher: str | None = None) -> dict:
        e: dict = {"hooks": [{"type": "command",
                              "command": f"bash \"$CLAUDE_PROJECT_DIR\"/.claude/harness/hooks/{script}"}]}
        if matcher:
            e["matcher"] = matcher
        return e

    if hooks_cfg.get("protect_compiled", True):
        settings_hooks["PreToolUse"] = [hook_entry("protect-compiled.sh", "Edit|Write|MultiEdit")]
    if hooks_cfg.get("session_context", True):
        settings_hooks["SessionStart"] = [hook_entry("session-context.sh")]
    if hooks_cfg.get("stop_test_gate", False):
        settings_hooks["Stop"] = [hook_entry("stop-test-gate.sh")]

    settings_payload = json.dumps(
        {"_managed_by": "harness", "hooks": settings_hooks}, indent=2) + "\n"
    settings_path = repo / ".claude/settings.json"
    if settings_path.exists() and '"_managed_by": "harness"' not in settings_path.read_text():
        write(".claude/harness/settings-hooks.json", settings_payload)
        print("note: .claude/settings.json exists and is not harness-managed — "
              "merge .claude/harness/settings-hooks.json into it by hand.")
    else:
        write(".claude/settings.json", settings_payload)

    # -- CLAUDE.md
    write("CLAUDE.md", render_claude_md(harness_root, cfg, kind, stacks_cfg))

    # -- lefthook
    lh = repo / "lefthook.yml"
    if not lh.exists():
        cmds = cfg.get("commands", {})
        scan = cfg.get("security", {}).get("secret_scan", "gitleaks")
        q = json.dumps  # YAML-safe scalar: commands routinely contain `:` and quotes
        write("lefthook.yml", LEFTHOOK_TEMPLATE.format(
            lint=q(cmds.get("lint", "echo no lint configured")),
            fmt=q(cmds.get("format", "echo no format configured")),
            test=q(cmds.get("test_fast", "echo no fast tests configured")),
            scan=scan))
    return out


def render_claude_md(harness_root: Path, cfg: dict, kind: str, stacks: list) -> str:
    prov = cfg.get("provider", {})
    return f"""# Harness-managed repository

Compiled by harness v{core_version(harness_root)} — DO NOT edit `.claude/harness/**`,
`.claude/agents/**` or `.claude/commands/**` by hand; edit the harness core and run
`harness update`. Repo-local rules go in `.harness/overrides/rules/`.

## This repo

- Provider: **{kind}** · org `{prov.get('organization', '?')}` · project
  `{prov.get('project', '?')}` · repo `{prov.get('repository', '?')}`
- Stacks: {', '.join(stacks)}
- Config: `harness.yaml` (commands, test-suites contract, architecture placement)

## Process (non-negotiable)

1. Work items are created only by the issue-writer (`/issue`) and gated at
   `harness:proposed`. Douglas approves upstream (`harness:approved`); nothing is
   developed from an unapproved item.
2. `/dev` runs the cycle: architects (if flagged) → test-engineer (failing BDD specs)
   → engineer → code review ∥ security review (comment-only, upstream) → QA builds
   suites → pipeline validates. Full definition:
   `.claude/harness/workflows/development-cycle.md`.
3. Gate state lives upstream as `harness:*` tags — mirror every transition immediately.
4. Tests before code. A test suite the pipeline doesn't run does not exist
   (`harness.yaml → test-suites`).
5. ADR/diagram placement: reach beyond this repo → global docs
   ({cfg.get('architecture', {}).get('global_docs') or 'not configured'}); repo-scope →
   `docs/architecture/`.

## Commands

`/issue` `/triage` `/dev` `/review` `/qa` `/adr` `/haiku` `/c4` `/solution-diagram`
`/pipeline` — each maps to an agent in `.claude/agents/`.

Provider recipes for all upstream operations: `.claude/harness/provider.md`.
"""


LEFTHOOK_TEMPLATE = """# Created by harness, then yours to evolve (secdevops owns it).
# The `run:` values that come from harness.yaml -> commands are re-propagated by
# `harness update` whenever they change there; everything else here is left alone.
pre-commit:
  parallel: true
  commands:
    lint:
      run: {lint}
    format:
      run: {fmt}
    secrets:
      run: "{scan} protect --staged --no-banner || {scan} git --staged --no-banner || true"

pre-push:
  commands:
    fast-tests:
      run: {test}
"""


# ---------------------------------------------------------------- stack changes

# Only these paths are compile output that `update` may delete when it stops being
# generated. lefthook.yml is deliberately NOT here: harness creates it once and the repo
# owns it from then on.
COMPILED_ROOTS = (".claude/", "CLAUDE.md")


def prune_orphans(repo: Path, before: dict, after: list[Path]) -> list[str]:
    """Drop compiled artifacts the current config no longer produces. Without this, a
    stack removed from harness.yaml leaves its `engineer-<stack>.md` on disk and Claude
    Code keeps routing to an agent for a stack the repo does not have."""
    keep = {str(p.relative_to(repo)) for p in after}
    gone = [rel for rel in before
            if rel not in keep and rel.startswith(COMPILED_ROOTS)]
    for rel in gone:
        f = repo / rel
        if f.is_file():
            f.unlink()
    return sorted(gone)


def drop_segment(chain: str, seg: str) -> tuple[str, bool]:
    """Remove one stack's link from a `a && b` chain, taking its separator with it."""
    for pat in (r"\s*&&\s*" + re.escape(seg) + r"(?![\w:./-])",   # not the first link
                r"^" + re.escape(seg) + r"\s*&&\s*",              # first of several
                r"^" + re.escape(seg) + r"\s*$"):                 # the only link
        out, n = re.subn(pat, "", chain, count=1)
        if n:
            return out.strip(), True
    return chain, False


def add_segment(chain: str, seg: str) -> str:
    if not chain.strip() or "TODO" in chain:
        return seg                                  # nothing real there to preserve
    return chain if seg in chain else f"{chain} && {seg}"


def set_command(text: str, key: str, value: str) -> str:
    """Rewrite one key inside the `commands:` block of harness.yaml, at text level so the
    user's comments and ordering survive. Scoped to the block: `format` must not match a
    key of the same name elsewhere."""
    m = re.search(r"^commands:.*?(?=^\S|\Z)", text, re.M | re.S)
    if not m:
        return text
    block = m.group(0)
    patched, n = re.subn(rf"^(\s*{re.escape(key)}:\s*).*?(\s*#.*)?$",
                         lambda mm: mm.group(1) + json.dumps(value) + (mm.group(2) or ""),
                         block, count=1, flags=re.M)
    return text[:m.start()] + patched + text[m.end():] if n else text


def sync_stacks(repo: Path, cfg: dict, previous: dict | None) -> tuple[list[str], dict]:
    """Reconcile `commands` with a hand-edited `stacks:` list. A stack added there gets
    its link appended to each chain; a stack removed has its link taken out — matching on
    the link the last install recorded, so the OTHER stacks' hand-tuned commands survive.
    Returns the report and the per-stack record for the manifest."""
    stacks = [str(s) for s in (cfg.get("stacks") or ["javascript"])]
    current = {s: stack_command_set(repo, s) for s in stacks}
    if previous is None:            # nothing recorded yet: no previous value to match on
        return ["  [note] first run recording the per-stack commands — stack changes "
                "propagate from the next `harness update`"], current

    added = [s for s in stacks if s not in previous]
    removed = [s for s in previous if s not in stacks]
    if not added and not removed:
        return [], current

    cfg_text = (repo / CONFIG).read_text()
    cmds = dict(cfg.get("commands") or {})
    report, missed = [], []
    for key in COMMAND_KEYS:
        chain = str(cmds.get(key, ""))
        before = chain
        for s in removed:
            seg = previous[s].get(key)
            if not seg:
                continue
            chain, hit = drop_segment(chain, seg)
            if not hit:
                missed.append(f"    [warn] {s}/{key}: {seg!r} not found in the chain — "
                              "rewritten by hand? left as is")
        for s in added:
            seg = current[s].get(key)
            if seg:
                chain = add_segment(chain, seg)
        if not chain.strip():
            chain = f"echo TODO: {key}"
        if chain != before:
            cfg_text = set_command(cfg_text, key, chain)
            report.append(f"  {key}: {before!r} → {chain!r}")

    if report:
        (repo / CONFIG).write_text(cfg_text)
    head = ", ".join([f"+{s}" for s in added] + [f"-{s}" for s in removed])
    return ([f"  stacks: {head}"] + report + missed) if (report or missed) else [], current


# ---------------------------------------------------------------- propagation

# harness.yaml is the source of truth for commands, but the places that actually RUN
# them hold copies: lefthook.yml and the pipeline files (the stop-test-gate hook reads
# harness.yaml live, so it needs nothing). `update` rewrites those copies when the value
# in harness.yaml changed, matching on the value the last install recorded in the
# manifest — so a hand-tuned pipeline keeps everything else it says.
PROPAGATION_TARGETS = ["lefthook.yml", "azure-pipelines.yml", ".gitlab-ci.yml"]


# Entries in lefthook.yml whose `run:` belongs to harness.yaml, not to the file.
LEFTHOOK_OWNED = {
    "lint": ["pre-commit", "commands", "lint", "run"],
    "format": ["pre-commit", "commands", "format", "run"],
    "test_fast": ["pre-push", "commands", "fast-tests", "run"],
}


def block_bounds(lines: list[str], start: int, end: int, key: str) -> tuple[int, int, int] | None:
    """Line range and indentation of `key:` between start and end, by indentation."""
    for i in range(start, end):
        m = re.match(r"^(\s*)" + re.escape(key) + r":", lines[i])
        if not m:
            continue
        indent = len(m.group(1))
        j = i + 1
        while j < end and (not lines[j].strip()
                           or len(lines[j]) - len(lines[j].lstrip()) > indent):
            j += 1
        return i, j, indent
    return None


def set_yaml_path(text: str, path: list[str], value: str) -> tuple[str, bool]:
    """Rewrite one scalar addressed by a key path, touching only its line — the rest of
    the file (comments, extra hooks, `glob:`/`parallel:` tuning) is left as it is."""
    lines = text.splitlines(keepends=True)
    start, end = 0, len(lines)
    for key in path:
        found = block_bounds(lines, start, end, key)
        if not found:
            return text, False
        i, j, indent = found
        start, end = i, j
    lines[start] = " " * indent + f"{path[-1]}: {json.dumps(value)}\n"
    return "".join(lines), True


def sync_lefthook(repo: Path, cfg: dict) -> list[str]:
    """harness.yaml wins for the `run:` of the entries harness put there. Unlike the
    pipeline files — arbitrary YAML, so they can only be matched by their previous value
    — lefthook.yml has a shape harness knows, so this needs no manifest history and
    repairs a copy that drifted for any reason."""
    lh = repo / "lefthook.yml"
    if not lh.exists():
        return []
    text = lh.read_text()
    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        return [f"  [warn] lefthook.yml does not parse ({yaml_error(text) or e}) — skipped"]

    cmds = cfg.get("commands") or {}
    report = []
    for key, path in LEFTHOOK_OWNED.items():
        want = str(cmds.get(key, "")).strip()
        if not want:
            continue
        node = doc
        for seg in path[:-1]:
            node = node.get(seg) or {} if isinstance(node, dict) else {}
        have = node.get("run") if isinstance(node, dict) else None
        if have is None:               # entry renamed or removed on purpose — respect it
            continue
        if str(have).strip() == want:
            continue
        text, ok = set_yaml_path(text, path, want)
        report.append(f"  {'/'.join(path[:-1])}: {str(have)!r} → {want!r}"
                      if ok else
                      f"  [warn] {key}: lefthook.yml carries {have!r} but the line could "
                      "not be rewritten — fix it by hand")
    if report:
        lh.write_text(text)
    return report


def propagation_files(repo: Path) -> list[Path]:
    files = [repo / f for f in PROPAGATION_TARGETS]
    gw = repo / ".github/workflows"
    if gw.is_dir():
        files += sorted(gw.glob("*.yml")) + sorted(gw.glob("*.yaml"))
    return [f for f in files if f.is_file()]


def swap_command(text: str, old: str, new: str) -> tuple[str, int]:
    """Replace `old` only where it is a whole command, never inside a longer one —
    `npm test` must not match the `npm test:integration` of a suite entry."""
    pat = re.compile(r"(?<![\w:./-])" + re.escape(old) + r"(?![\w:./-])")
    return pat.subn(lambda _: new, text)


def yaml_error(text: str) -> str:
    """Empty if the text parses; otherwise the parser's one-line complaint."""
    try:
        yaml.safe_load(text)
        return ""
    except yaml.YAMLError as e:
        return str(getattr(e, "problem", None) or str(e).splitlines()[0]).strip()


def swap_in_yaml(text: str, old: str, new: str) -> tuple[str, int, str]:
    """Swap the command, keeping the host file parseable. A copy living inside a quoted
    scalar (`run: "npm test"`) breaks when the new command carries quotes of its own, so
    that case re-quotes the whole scalar instead of patching its insides."""
    swapped, n = swap_command(text, old, new)
    if not n:
        return text, 0, ""
    err = yaml_error(swapped)
    if not err:
        return swapped, n, ""
    requoted, m = re.subn('"' + re.escape(old) + '"', lambda _: json.dumps(new), text)
    if m and not yaml_error(requoted):
        return requoted, m, ""
    return text, 0, err


def recorded_commands(cfg: dict) -> dict[str, str]:
    """Every command the repo declares, flat: the four ops plus the test-suite commands,
    which the pipeline contract wires into stages the same way."""
    cmds = {k: str(v) for k, v in (cfg.get("commands") or {}).items() if v}
    for s in cfg.get("test-suites") or []:
        if s.get("name") and s.get("command"):
            cmds[f"test-suites.{s['name']}"] = str(s["command"])
    return cmds


def propagate_commands(repo: Path, cfg: dict, previous: dict | None) -> list[str]:
    """Push changed commands into the files that carry copies. Returns report lines."""
    current = recorded_commands(cfg)
    if previous is None:            # nothing recorded yet: no previous value to match on
        return ["  [note] first run recording the commands — pipeline files propagate "
                "from the next `harness update` (lefthook.yml is synced either way)"]
    changed = {k: (previous[k], v) for k, v in current.items()
               if k in previous and previous[k] != v}
    if not changed:
        return []

    report = []
    for key, (old, new) in changed.items():
        report.append(f"  {key}: {old!r} → {new!r}")
        hits, warns = [], []
        for f in propagation_files(repo):
            swapped, n, err = swap_in_yaml(f.read_text(), old, new)
            if n:
                f.write_text(swapped)
                hits.append(f"{f.relative_to(repo)} ({n})")
            elif err:
                warns.append(f"    [warn] would break {f.relative_to(repo)} "
                             f"({err}) — left untouched, fix it by hand")
        report.append("    " + (", ".join(hits) if hits else
                                "[warn] no file carried the old value — nothing updated"))
        report += warns
    return report


# ---------------------------------------------------------------- install / update

def cmd_install(args: argparse.Namespace) -> None:
    repo = Path(args.repo).resolve()
    cfg = load_config(repo)
    harness_root = find_core(args.core, cfg)
    tool = args.tool
    if tool != "claude-code":
        fail(f"tool '{tool}' is on the roadmap; only claude-code is compiled today.")
    # validated before anything is written: a typo in `stacks:` must not get as far as
    # rewriting the command chains and only then fail in the compiler
    known = {f.stem for f in (harness_root / "core" / "stacks").glob("*.md")}
    unknown = [s for s in (cfg.get("stacks") or []) if s not in known]
    if unknown:
        fail(f"unknown stack in {CONFIG}: {', '.join(unknown)} "
             f"(known: {', '.join(sorted(known))})")

    mpath = repo / MANIFEST
    prev = json.loads(mpath.read_text()) if mpath.exists() else {}

    # stacks first: a stack added or removed by hand rewrites the command chains in
    # harness.yaml, and everything downstream must compile from the reconciled config
    stack_report, stack_cmds = sync_stacks(repo, cfg, prev.get("stack_commands"))
    if stack_report:
        cfg = load_config(repo)

    files = compile_claude_code(harness_root, repo, cfg)
    # both before the manifest is hashed, or a rewritten file reads as drifted
    pruned = prune_orphans(repo, prev.get("files") or {}, files)
    report = propagate_commands(repo, cfg, prev.get("commands"))
    # last word on lefthook.yml: structural, so it converges even when there is no
    # previous value to match on (a repo installed before the manifest recorded them)
    lh_report = sync_lefthook(repo, cfg)

    version = core_version(harness_root)
    manifest = {
        "tool": tool,
        "core_version": version,
        "compiled_at": date.today().isoformat(),
        "commands": recorded_commands(cfg),
        "stack_commands": stack_cmds,
        "files": {str(p.relative_to(repo)): sha256(p) for p in files},
    }
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, indent=2) + "\n")

    # record core_version in harness.yaml (text-level, keep comments intact)
    cfg_text = (repo / CONFIG).read_text()
    cfg_text = re.sub(r'core_version:\s*"[^"]*"', f'core_version: "{version}"', cfg_text)
    (repo / CONFIG).write_text(cfg_text)

    print(f"compiled {len(files)} files for {tool} (core v{version}).")
    if pruned:
        print(f"removed {len(pruned)} artifact(s) this config no longer generates:")
        print("\n".join(f"  {rel}" for rel in pruned))
    if stack_report:
        print("reconciled commands with the stack list in harness.yaml:")
        print("\n".join(stack_report))
    if report:
        print("propagated command changes from harness.yaml:")
        print("\n".join(report))
    if lh_report:
        print("synced lefthook.yml with harness.yaml:")
        print("\n".join(lh_report))
    if shutil.which("lefthook"):
        subprocess.run(["lefthook", "install"], cwd=repo, check=False)
    else:
        print("note: lefthook binary not found — install it and run `lefthook install`.")


def cmd_update(args: argparse.Namespace) -> None:
    repo = Path(args.repo).resolve()
    mpath = repo / MANIFEST
    if not mpath.exists():
        fail("no manifest found — run `harness install` first.")
    args.tool = json.loads(mpath.read_text())["tool"]
    cmd_install(args)


# ---------------------------------------------------------------- provider-setup

def cmd_provider_setup(args: argparse.Namespace) -> None:
    """Create the vocabulary the adapter needs upstream. Idempotent; mutates the remote."""
    repo = Path(args.repo).resolve()
    cfg = load_config(repo)
    kind = cfg.get("provider", {}).get("kind")
    if kind not in LABEL_BASED_PROVIDERS:
        print(f"provider '{kind}' carries item type and gate state in native fields — "
              "nothing to bootstrap.")
        return
    if kind == "gitlab":
        fail("gitlab bootstrap is not implemented yet — see providers/gitlab.md.")

    slug = repo_slug(cfg)
    if "/" not in slug or slug.startswith("/") or slug.endswith("/"):
        fail(f"harness.yaml must set provider.organization (owner) and "
             f"provider.repository — got '{slug}'.")
    if shutil.which("gh") is None:
        fail("`gh` not found — install the GitHub CLI first.")

    labels = expected_labels(cfg)
    print(f"bootstrapping {len(labels)} labels on {slug}"
          + (" (dry run)" if args.dry_run else ""))
    failed = []
    for name in labels:
        color, desc = LABEL_STYLE.get(name, ("EDEDED", "Harness label"))
        cmd = ["gh", "label", "create", name, "--color", color,
               "--description", desc, "--force", "-R", slug]
        if args.dry_run:
            print(f"  would run: {shlex.join(cmd)}")
            continue
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            print(f"  [ok ] {name}")
        else:
            failed.append(name)
            print(f"  [FAIL] {name} — {last_line(r.stderr or r.stdout)}")
    if failed:
        fail(f"{len(failed)} label(s) could not be created: {', '.join(failed)}")
    if not args.dry_run:
        print("labels ready. Next: `harness install --tool claude-code` (or `harness doctor`).")


# ---------------------------------------------------------------- doctor

def check(ok: bool, label: str, detail: str = "") -> bool:
    mark = "ok " if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def cmd_doctor(args: argparse.Namespace) -> None:
    repo = Path(args.repo).resolve()
    failures = 0
    print(f"harness doctor — {repo}")

    cfg = load_config(repo)
    failures += not check(True, "harness.yaml parses")

    harness_root = find_core(args.core, cfg)
    installed = cfg.get("harness", {}).get("core_version", "?")
    current = core_version(harness_root)
    failures += not check(installed == current, "core version",
                          f"installed {installed}, core {current}"
                          + ("" if installed == current else " → run `harness update`"))

    if __version__ != current:
        print(f"  [warn] harness-cli {__version__} but core is {current} — this repo "
              "locks the two; run `pipx reinstall harness-cli`")

    gates = cfg.get("provider", {}).get("gate_tags", [])
    failures += not check(set(GATE_TAGS) <= set(gates), "gate tags intact",
                          "missing: " + ", ".join(sorted(set(GATE_TAGS) - set(gates)))
                          if not set(GATE_TAGS) <= set(gates) else "")

    # commands gate every commit (lefthook) and the CI-on-PR stage: an `echo TODO`
    # placeholder passes both, so it reads as green while nothing is being checked.
    cmds = cfg.get("commands") or {}
    unset = [k for k in COMMAND_KEYS
             if not str(cmds.get(k, "")).strip() or "TODO" in str(cmds.get(k, ""))]
    failures += not check(not unset, "commands configured",
                          "placeholder/missing: " + ", ".join(unset) if unset else "")

    # provider CLI auth
    kind = cfg.get("provider", {}).get("kind")
    cli, auth_cmd = {
        "azure-devops": ("az", ["az", "account", "show", "-o", "none"]),
        "github": ("gh", ["gh", "auth", "status"]),
        "gitlab": ("glab", ["glab", "auth", "status"]),
    }.get(kind, (None, None))
    authed = False
    if cli:
        present = shutil.which(cli) is not None
        failures += not check(present, f"provider CLI `{cli}` installed")
        if present:
            r = subprocess.run(auth_cmd, capture_output=True, text=True)
            authed = r.returncode == 0
            failures += not check(authed, f"`{cli}` authenticated",
                                  "" if authed else "login/PAT needed")
            if kind == "github" and authed:
                scopes = (r.stdout or "") + (r.stderr or "")
                if "workflow" not in scopes:
                    print("  [warn] token lacks the `workflow` scope — secdevops cannot "
                          "push .github/workflows/** (`gh auth refresh -s workflow`)")
    else:
        failures += not check(False, "provider kind known", str(kind))

    # label vocabulary must exist upstream before any item can be created
    if kind in LABEL_BASED_PROVIDERS:
        want = expected_labels(cfg)
        if kind == "github" and authed:
            slug = repo_slug(cfg)
            r = subprocess.run(["gh", "label", "list", "-R", slug, "--limit", "200",
                                "--json", "name", "--jq", ".[].name"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                failures += not check(False, "provider labels readable",
                                      f"{slug}: {last_line(r.stderr)}")
            else:
                have = {ln.strip() for ln in r.stdout.splitlines() if ln.strip()}
                missing = [x for x in want if x not in have]
                failures += not check(not missing, "provider labels bootstrapped",
                                      "missing: " + ", ".join(missing)
                                      + " → run `harness provider-setup`" if missing else "")
        else:
            print(f"  [note] {len(want)} labels required upstream "
                  "(`harness provider-setup`) — not verified without CLI auth")
    if kind == "github":
        print("  [note] github rejects self-approval on PRs: reviewers post "
              "[harness:approved-by:*] / [harness:changes-requested] marker comments. "
              "Native `gh pr review --approve` needs a separate reviewer identity.")

    # manifest drift
    mpath = repo / MANIFEST
    if check(mpath.exists(), "compiled manifest present"):
        manifest = json.loads(mpath.read_text())
        drift = [rel for rel, h in manifest["files"].items()
                 if not (repo / rel).exists() or sha256(repo / rel) != h]
        failures += not check(not drift, "compiled artifacts unmodified",
                              f"{len(drift)} drifted (hand-edited?): "
                              + ", ".join(drift[:5]) if drift else "")
    else:
        failures += 1

    # test-suites contract
    suites = cfg.get("test-suites") or []
    pipeline_files = [p for p in [repo / "azure-pipelines.yml", repo / ".gitlab-ci.yml"]
                      if p.exists()]
    gw = repo / ".github/workflows"
    if gw.is_dir():
        pipeline_files += list(gw.glob("*.yml")) + list(gw.glob("*.yaml"))
    pipeline_text = "\n".join(p.read_text() for p in pipeline_files)
    for s in suites:
        pth = repo / s.get("path", "")
        failures += not check(pth.exists(), f"suite '{s['name']}' path exists", s.get("path", ""))
        wired = f"[suite:{s['name']}]" in pipeline_text or s.get("command", "\x00") in pipeline_text
        failures += not check(wired, f"suite '{s['name']}' wired to a pipeline stage",
                              "" if wired else f"declared stage '{s.get('stage')}' not found in pipeline files")
    if not suites:
        print("  [note] no test-suites declared yet (fine for a new repo)")

    # toggle registry expiry
    reg = repo / str(cfg.get("toggles", {}).get("registry", "docs/toggles.md"))
    if reg.exists():
        today = date.today().isoformat()
        expired = [m.group(1) for m in re.finditer(
            r"Expiry / review:\*{0,2}\s*(\d{4}-\d{2}-\d{2})", reg.read_text())
            if m.group(1) < today]
        failures += not check(not expired, "no expired toggles",
                              ", ".join(expired) if expired else "")

    # lefthook (warning only — the binary may live per-machine)
    if shutil.which("lefthook") is None or not (repo / "lefthook.yml").exists():
        print("  [warn] lefthook not fully set up (binary + lefthook.yml + `lefthook install`)")
    else:
        check(True, "lefthook present")

    print(f"\n{'all checks passed' if failures == 0 else f'{failures} check(s) failed'}")
    sys.exit(1 if failures else 0)


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(prog="harness", description=__doc__)
    ap.add_argument("--repo", default=".", help="target project repo (default: cwd)")
    ap.add_argument("--core", help="path to the harness repo checkout")
    ap.add_argument("-V", "--version", action=VersionAction,
                    help="print the CLI and core versions")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="write harness.yaml + docs skeleton into a repo")
    p.add_argument("--provider", default="azure-devops",
                   choices=["azure-devops", "github", "gitlab"])
    p.add_argument("--organization")
    p.add_argument("--project")
    p.add_argument("--repository")
    p.add_argument("--stacks", help="comma-separated: javascript,csharp,python,rust")
    p.add_argument("--no-detect", action="store_true",
                   help="skip reading the repo; use the stacks' default commands")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("install", help="compile the core into the repo for a tool")
    p.add_argument("--tool", default="claude-code")
    p.set_defaults(fn=cmd_install)

    p = sub.add_parser("update", help="recompile with the current core")
    p.set_defaults(fn=cmd_update)

    p = sub.add_parser("provider-setup",
                       help="create the harness labels upstream (github/gitlab)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the commands without touching the remote")
    p.set_defaults(fn=cmd_provider_setup)

    p = sub.add_parser("doctor", help="config, auth, drift and contract checks")
    p.set_defaults(fn=cmd_doctor)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
