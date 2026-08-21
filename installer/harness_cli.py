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
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

MANIFEST = ".harness/manifest.json"
CONFIG = "harness.yaml"
GATE_TAGS = [
    "harness:proposed", "harness:approved", "harness:in-dev",
    "harness:in-review", "harness:done", "harness:needs-revision",
]


# ---------------------------------------------------------------- helpers

def fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)


def find_core(explicit: str | None, cfg: dict | None) -> Path:
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
    fail("cannot locate the harness repo (core/). Use --core or set HARNESS_HOME.")
    raise AssertionError


def load_config(repo: Path) -> dict:
    p = repo / CONFIG
    if not p.exists():
        fail(f"{CONFIG} not found in {repo}. Run `harness init` first.")
    try:
        return yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as e:
        fail(f"{CONFIG} is not valid YAML: {e}")
    raise AssertionError


def core_version(harness_root: Path) -> str:
    return (harness_root / "core" / "VERSION").read_text().strip()


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

commands:
  lint: "echo TODO: lint"
  format: "echo TODO: format"
  test_fast: "echo TODO: fast tests"
  build: "echo TODO: build"

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
    stacks = args.stacks.split(",") if args.stacks else ["javascript"]
    cfg_path.write_text(INIT_TEMPLATE.format(
        version=core_version(harness_root),
        core_path=str(harness_root),
        provider=args.provider,
        org=args.organization or "https://dev.azure.com/YOUR_ORG",
        project=args.project or "YourProject",
        repo_name=args.repository or repo.name,
        gates=", ".join(GATE_TAGS),
        stacks="".join(f"  - {s.strip()}\n" for s in stacks),
    ))
    for d in ["docs/architecture/adrs", "docs/architecture/diagrams",
              ".harness/overrides/rules"]:
        (repo / d).mkdir(parents=True, exist_ok=True)
    reg = repo / "docs" / "toggles.md"
    if not reg.exists():
        reg.write_text("# Feature toggle registry\n\n(see harness "
                       "core/templates/toggles/feature-toggle.md)\n")
    print(f"initialized: {cfg_path}")
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
    for p in sorted((core / "templates" / "pipelines").glob("*")):
        write(f".claude/harness/templates/pipelines/{p.name}", p.read_text())

    # provider adapter (+ interface)
    kind = cfg.get("provider", {}).get("kind", "azure-devops")
    adapter = harness_root / "providers" / f"{kind}.md"
    if not adapter.exists():
        fail(f"unknown provider kind: {kind}")
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


LEFTHOOK_TEMPLATE = """# Managed by harness (created once; evolve via secdevops agent)
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


# ---------------------------------------------------------------- install / update

def cmd_install(args: argparse.Namespace) -> None:
    repo = Path(args.repo).resolve()
    cfg = load_config(repo)
    harness_root = find_core(args.core, cfg)
    tool = args.tool
    if tool != "claude-code":
        fail(f"tool '{tool}' is on the roadmap; only claude-code is compiled today.")
    files = compile_claude_code(harness_root, repo, cfg)

    version = core_version(harness_root)
    manifest = {
        "tool": tool,
        "core_version": version,
        "compiled_at": date.today().isoformat(),
        "files": {str(p.relative_to(repo)): sha256(p) for p in files},
    }
    mpath = repo / MANIFEST
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, indent=2) + "\n")

    # record core_version in harness.yaml (text-level, keep comments intact)
    cfg_text = (repo / CONFIG).read_text()
    cfg_text = re.sub(r'core_version:\s*"[^"]*"', f'core_version: "{version}"', cfg_text)
    (repo / CONFIG).write_text(cfg_text)

    print(f"compiled {len(files)} files for {tool} (core v{version}).")
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

    gates = cfg.get("provider", {}).get("gate_tags", [])
    failures += not check(set(GATE_TAGS) <= set(gates), "gate tags intact",
                          "missing: " + ", ".join(sorted(set(GATE_TAGS) - set(gates)))
                          if not set(GATE_TAGS) <= set(gates) else "")

    # provider CLI auth
    kind = cfg.get("provider", {}).get("kind")
    cli, auth_cmd = {
        "azure-devops": ("az", ["az", "account", "show", "-o", "none"]),
        "github": ("gh", ["gh", "auth", "status"]),
        "gitlab": ("glab", ["glab", "auth", "status"]),
    }.get(kind, (None, None))
    if cli:
        present = shutil.which(cli) is not None
        failures += not check(present, f"provider CLI `{cli}` installed")
        if present:
            r = subprocess.run(auth_cmd, capture_output=True)
            failures += not check(r.returncode == 0, f"`{cli}` authenticated",
                                  "" if r.returncode == 0 else "login/PAT needed")
    else:
        failures += not check(False, "provider kind known", str(kind))

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
        pipeline_files += list(gw.glob("*.yml"))
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
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="write harness.yaml + docs skeleton into a repo")
    p.add_argument("--provider", default="azure-devops",
                   choices=["azure-devops", "github", "gitlab"])
    p.add_argument("--organization")
    p.add_argument("--project")
    p.add_argument("--repository")
    p.add_argument("--stacks", help="comma-separated: javascript,csharp,python")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("install", help="compile the core into the repo for a tool")
    p.add_argument("--tool", default="claude-code")
    p.set_defaults(fn=cmd_install)

    p = sub.add_parser("update", help="recompile with the current core")
    p.set_defaults(fn=cmd_update)

    p = sub.add_parser("doctor", help="config, auth, drift and contract checks")
    p.set_defaults(fn=cmd_doctor)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
