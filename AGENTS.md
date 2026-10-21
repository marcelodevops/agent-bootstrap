# AGENTS.md — agent-bootstrap (`projboot`)

Scaffold AI-agent-ready projects from curated language templates, customizable workflow presets, or a dirtree layout.

## Profile & Working Commands

- **Profile**: `python` CLI package (`bootstrapper/` package, entrypoints `projboot` and `agent-bootstrap`)
- **Setup**: `uv sync --extra dev` (or `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`)
- **Run**: `uv run projboot --help` (or `uv run agent-bootstrap --help`)
- **Test**: `uv run --extra dev pytest -q`
- **Build**: `uv run --extra dev python -m build`

## Repository Layout

- `pyproject.toml`, `README.md`, `LICENSE` — package metadata, CLI documentation, and license
- `bootstrapper/cli.py`, `bootstrapper/__main__.py` — Typer CLI commands (`create`, `preview`, `config-init`, `list-presets`, `list-templates`, plus deprecated `init` / `init-from-tree`), atomic staging, and preflight collision validation
- `bootstrapper/composer.py` — layered file composition (`base template` + `architecture layout` + `universal harness` + `assistant overlays` + `license`) and post-scaffold hooks (`git` and `graphify`)
- `bootstrapper/templates.py` — `string.Template` rendering, `$pkg_name` / `$helm_name` / `$description_json` derivation, language templates (`python-microservice`, `typescript`, `helm-chart`, `none`), and structural `--arch` layer generators
- `bootstrapper/agents.py` — `AGENTS.md` and stack-aware assistant overlay generators (`claude`, `gh-copilot`, `codeassistant`, `cursor`)
- `bootstrapper/presets.py` — `PresetConfig`, `~/.config/projboot/` loader, and secret/symlink boundary guards
- `bootstrapper/dirtree.py` — Unicode/ASCII `tree` listing parser
- `bootstrapper/github_utils.py` — PyGithub repository creation helper
- `tests/` — behavioral and native-toolchain verification suite
- `AGENTS.md`, `PROMPTS.md`, `.remember/MEMORY.md`, `.remember/decisions.md`, `.agents/skills/project-conventions/SKILL.md` — dogfooded agent harness

## Change Boundaries & Hygiene

- Validate all inputs and output path collisions before touching the filesystem or network.
- Keep `create` and `preview` sharing `_resolve_options_and_compose` and `_validate_write_plan` so `preview` is always side-effect-free and matches `create`.
- Never commit `.env` or personal credentials; run `uv run --extra dev pytest -q` before claiming any change is complete.
