---
stack-id: python
stack-name: Python
---
- Python version from the repo (`pyproject.toml`); type hints on all new code, checked
  with the repo's checker (mypy/pyright).
- BDD: pytest-bdd. Unit: pytest, plain asserts, fixtures over setup classes.
- Lint/format: ruff (lint + format) via `commands.lint` / `commands.format`.
- Pydantic (or dataclasses) at trust boundaries; no naked dicts crossing module lines.
- Dependencies through the repo's manager (uv/poetry/pip-tools) — never a bare
  `pip install` without a lock update.
