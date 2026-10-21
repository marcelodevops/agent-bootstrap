# Architectural & Product Decisions (agent-bootstrap)

Log key technical decisions chronologically so agents preserve context across sessions.

## 2026-10-20 — Product Cleanup & Dogfooding
- Replaced hardcoded `src/appstarter/` Python package with dynamic `src/$pkg_name/` derived from `$name`.
- Made `--arch` (`hexagonal`, `clean-architecture`, `layered`) generate real structural subpackages for Python and TypeScript.
- Removed the non-runnable experimental `rails` template.
- Added `--from-tree / -t` to `create` and `preview` and marked legacy `init` / `init-from-tree` commands as deprecated aliases.
- Dogfooded the `agent-bootstrap` harness (`AGENTS.md`, `PROMPTS.md`, `.remember/`, `.agents/skills/`) in the repository root.
