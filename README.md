# agent-bootstrap (`projboot`)

[![PyPI](https://img.shields.io/pypi/v/agent-bootstrap)](https://pypi.org/project/agent-bootstrap/)
[![Python](https://img.shields.io/pypi/pyversions/agent-bootstrap)](https://pypi.org/project/agent-bootstrap/)

Scaffold AI-agent-ready projects from curated language templates, customizable workflow presets, or a `tree`-style layout — locally first, with one-command GitHub repository creation.

## Install

Install globally as an isolated CLI tool with `uv` (recommended) or `pipx`, or via `pip`:

```bash
uv tool install agent-bootstrap      # installs `projboot` and `agent-bootstrap` globally
# or from a local checkout:
uv tool install --force -e .

# or via pip:
pip install agent-bootstrap          # installs both `projboot` and `agent-bootstrap`
pip install -e ".[dev]"              # dev: + pytest & build
```

Requires Python 3.11+. Local scaffolding needs no token and no network; GitHub remote creation (`-r github --create`) uses `GITHUB_TOKEN`.

---

## Quickstart: Preview & AI Agent Project Bootstrapping (`projboot preview` / `projboot create`)

### 1. Initialize your personal presets and skills store

```bash
projboot config-init
projboot list-presets
```

### 2. Preview the composed file tree and planned actions

`projboot preview` runs in memory. It does not write files, run `git` or Graphify, install dependencies, or access GitHub.

```bash
projboot preview demo-agent -l python -a claude -a gh-copilot --arch hexagonal
```

### 3. Create a local AI-agent project

```bash
projboot create demo-agent \
  -l python \
  -a claude -a gh-copilot \
  --arch hexagonal \
  --outputs-dir artifacts/out \
  --scripts-dir hack \
  --prompts-file PROMPTS.md
```

You can also merge additional layout paths from a `tree`-style file directly during `create` or `preview`:

```bash
projboot create demo-agent -l python --from-tree examples/tree.txt --gitkeep -a claude
```

### 4. Create a GitHub repository and push one Git history

With `GITHUB_TOKEN` set, `--create` connects the local checkout and pushes its initial commit. `--clone` is retained as a compatibility flag and is not required.

```bash
projboot create new-project -l python -a claude -a gh-copilot -r github --create
```

With `--no-git`, the repository is created or selected without pushing; its existing contents are not inspected. `--force` allows selecting an existing repository, but the normal push never rewrites remote history.

### What `projboot create` Generates

1. **Base Language Stack (`-l / --lang`)**:
   - `python` / `python-microservice`: installable Python package in `src/<pkg_name>/` (where `<pkg_name>` is automatically derived as a valid Python identifier from `<name>`, e.g. `demo-agent` $\rightarrow$ `src/demo_agent/`) with console script `<pkg_name>`, module entrypoint `python -m <pkg_name>`, `tests/test_<pkg_name>.py`, `pyproject.toml`, `Dockerfile`, and GitHub CI running `pytest` + `python -m build`.
   - `typescript`: `package.json`, `tsconfig.json` (`ES2022` / `nodenext`), `src/index.ts`, multi-stage `Dockerfile`.
   - `helm-chart`: `Chart.yaml`, `values.yaml`, `templates/`, `helm lint` CI.
   - `none`: Minimal agent-only repo (`README.md` + `.gitignore`).
2. **Architectural Layer Scaffolding (`--arch`)**:
   - `modular` (default): clean baseline package layout.
   - `hexagonal` / `ports-and-adapters`: scaffolds `domain/`, `ports/`, and `adapters/` packages under `src/<pkg_name>/` (Python) or `src/` (TypeScript).
   - `clean-architecture` / `clean-arch`: scaffolds `domain/`, `use_cases/`, `interfaces/`, and `infrastructure/` packages.
   - `layered`: scaffolds `api/`, `services/`, and `repositories/` packages.
3. **Universal Agent Harness (Always Included)**:
   - `AGENTS.md`: Project overview, `$arch` rules and scaffolded layer directories, directory map (`$outputs_dir/`, `$scripts_dir/`, `$prompts_file`), and conditional `graphify` instructions (omitted when `--no-graphify` is set).
   - `graphify-out/`: Knowledge graph placeholder (`graphify-out/.gitkeep` unless `--no-graphify` is passed; only populated if the external `graphify` CLI is installed and `graphify update .` succeeds).
   - `.remember/`: Persistent agent memory (`MEMORY.md` & `decisions.md`, or copied from `~/.config/projboot/remember/`).
   - `.agents/skills/`: Reusable project skills (copied from `~/.config/projboot/skills/` or starter `project-conventions/SKILL.md`).
   - `$prompts_file` (default `PROMPTS.md`): Ordered prompt catalog.
   - `$outputs_dir/` & `$scripts_dir/` directories.
4. **Stack-Aware Assistant Overlays (`-a / --agent`, repeatable)**:
   - `-a claude`: `CLAUDE.md` (stack conventions and `@AGENTS.md` / `@.remember/MEMORY.md` references) + `.claude/settings.json`.
   - `-a gh-copilot`: `.github/copilot-instructions.md` + `.github/prompts/bootstrap.prompt.md`.
   - `-a codeassistant`: `.codeassistant/instructions.md` (custom/legacy instruction-file adapter kept for compatibility; does not claim undocumented native client auto-loading).
   - `-a cursor`: `.cursor/rules/project.mdc` (YAML frontmatter with quoted `globs` and `alwaysApply: true`).
   - *Verification scope*: automated tests verify static format decoding (JSON and YAML frontmatter parsing) of generated overlay files; live native client behavior must be verified in the respective assistant client.

### Post-Generation Summary, First Steps & User-Run Checks

`projboot create` does not execute generated code, install dependencies, or run project test suites automatically. After writing the scaffold, it prints a concise summary separating generated files, actual hook/remote status, and copy-pasteable next steps:
- `python` / `python-microservice`:
  - Setup & run: `cd <name> && python -m venv .venv && source .venv/bin/activate && pip install -e . && <pkg_name>` (or `python -m <pkg_name>`)
  - Verification checks: `pip install pytest && pytest` and `pip install build && python -m build`
- `typescript`:
  - Setup, build & run: `cd <name> && npm install && npm run build && npm start` (no test runner or `test` script is pre-configured in `package.json`)
- `helm-chart`:
  - Verification checks: `cd <name> && helm lint . && helm template <name> .` (local chart validation only; cluster deployment is not configured)
- `none`:
  - Agent harness only (`AGENTS.md`, `PROMPTS.md`, `.remember/`, `.agents/skills/`); no language runtime, build, or test commands apply.

---

## Presets & Personal User Store (`~/.config/projboot/`)

Initialize your personal `projboot` configuration directory (or set `PROJBOOT_HOME` to customize its path):

```bash
projboot config-init
projboot list-presets
```

This creates:
- `~/.config/projboot/presets.toml` — Define named presets (`default`, `clean-arch`, or your own) with default `arch`, `outputs_dir`, `scripts_dir`, `prompts_file`, and `agents`:
  ```toml
  [presets.default]
  arch = "modular"
  outputs_dir = "outputs"
  scripts_dir = "scripts"
  prompts_file = "PROMPTS.md"
  agents = []

  [presets.clean-arch]
  arch = "clean-architecture"
  outputs_dir = "artifacts/outputs"
  scripts_dir = "scripts"
  prompts_file = "docs/PROMPTS.md"
  agents = ["claude", "gh-copilot"]
  ```
- `~/.config/projboot/skills/` — Any skill files placed here are automatically copied into `.agents/skills/` and rendered with your project's `$name`, `$pkg_name`, `$arch`, `$outputs_dir`, `$scripts_dir`, and `$prompts_file` variables.
- `~/.config/projboot/remember/` — Starter memory templates copied into `.remember/` on every new project.

Use a named preset with `-p / --preset`:

```bash
projboot create my-service -l python -p clean-arch
```

---

## Legacy Template & Dirtree Commands

`projboot create` is the primary command (and supports `--from-tree / -t`). Legacy `init` and `init-from-tree` commands remain available for backwards compatibility:

```bash
projboot list-templates
projboot init --name my-svc --template python-microservice --local
projboot init-from-tree --name myproject --tree-file examples/tree.txt --gitkeep --local
```

---

## How Templating Works

Templates render with Python's `string.Template` (`$name`, `$pkg_name`, `$helm_name`, `$description`, `$year`, `$holder`, `$arch`, `$outputs_dir`, `$scripts_dir`, `$prompts_file`, plus any `--var`). This is deliberate: Helm's Go-template syntax (`{{ .Values.foo }}`) and GitHub Actions expressions (`${{ secrets.X }}`) contain no bare `$identifier`, so they pass through untouched.

## Tests

```bash
pytest -q
```
