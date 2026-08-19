---
rule: security
applies-to: [security-reviewer, engineer, secdevops]
---

# Security rules

Anchored on **OWASP Top 10** and **OWASP ASVS** — level from `harness.yaml`
(`security.asvs_level`: 1 default, 2 for sensitive repos).

- **Immediate blockers** (no discussion): secret/credential in code or history;
  injection path (SQL/NoSQL/command/template) reachable from input; authz check missing
  on a mutating endpoint; sensitive data written to logs.
- **Merge blockers:** vulnerable direct dependency with known exploit (fix or pin +
  dated exception on the item); disabled TLS verification; homemade crypto; CORS `*`
  on authenticated APIs.
- **Review checklist per PR:** input validation at trust boundaries · authn/authz on
  every new route/handler · output encoding · secret handling (env/vault, never code) ·
  dependency diff (`lock` file changes get read, not skimmed) · SSRF on any
  server-side fetch of user-supplied URLs · error messages don't leak internals.
- **Design-level review** when the item is tagged `security-review`: threat-model the
  change (STRIDE-lite: what can be spoofed/tampered/leaked here?) before code exists.
- **Exceptions are ADRs.** Accepted risk gets an owner, an expiry date and a
  compensating control, recorded per `rules/architecture.md`. Chat approval is not
  an exception.
