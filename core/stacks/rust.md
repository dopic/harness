---
stack-id: rust
stack-name: Rust
---
- Edition and toolchain from the repo (`Cargo.toml`, `rust-toolchain.toml`); pin the
  toolchain so CI, humans and agents build with the same compiler.
- BDD: cucumber-rs. Unit: `#[test]` next to the code; integration tests under `tests/`.
- Lint/format: `cargo clippy` with warnings denied + `cargo fmt` via `commands.lint` /
  `commands.format` — clippy findings are fixed, not `#[allow]`-ed without a reason.
- Errors are values: `Result` with `thiserror` at library boundaries, `anyhow` only in
  binaries. No `unwrap`/`expect`/`panic!` on any path reachable from untrusted input.
- Async: the runtime the repo already uses (tokio by default); never block inside an
  async fn (`spawn_blocking`), and timeouts on every external call.
- `unsafe` requires an ADR and a `// SAFETY:` comment stating the invariant upheld.
- Dependencies through `cargo add` with `Cargo.lock` committed; new crates justified in
  the PR and cleared by `cargo audit` / `cargo deny`.
