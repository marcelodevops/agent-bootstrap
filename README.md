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

Preview runs in memory. It does not write files, run `git` or Graphify, install dependencies, or access GitHub.

```bash
projboot preview demo-agent -l python -a claude -a gh-copilot
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

### 4. Create a GitHub repository and push one Git history

With `GITHUB_TOKEN` set, `--create` connects the local checkout and pushes its initial commit. `--clone` is retained as a compatibility flag and is not required.

```bash
projboot create new-project -l python -a claude -a gh-copilot -r github --create
```

With `--no-git`, the repository is created or selected without pushing; its existing contents are not inspected. `--force` allows selecting an existing repository, but the normal push never rewrites remote history.

### What `projboot create` Generates

1. **Base Language Stack (`-l / --lang`)**:
   - `python` / `python-microservice`: installable **starter** (not a production microservice) — `src/appstarter/` package with both documented run paths (the `appstarter` console script and `python -m appstarter`), `tests/`, `pyproject.toml`, `Dockerfile`, GitHub CI running `pytest` + `python -m build`. The import package is deliberately named `appstarter` regardless of the project name, so hyphenated identities like `my-app` still yield a stable `import appstarter`
   - `typescript`: `package.json`, `tsconfig.json`, `src/index.ts`, multi-stage `Dockerfile`
   - `helm-chart`: `Chart.yaml`, `values.yaml`, `templates/`, `helm lint` CI
   - `rails`: **EXPERIMENTAL layout only — not a runnable Rails app.** A partial sketch (`Gemfile`, `config.ru`, `config/application.rb`, one controller); `config/environment.rb`, `config/boot.rb`, `config/routes.rb`, `bin/rails`, `Rakefile`, `app/views/` and `db/` are absent, and `rails` `~> 7.1` additionally needs Ruby >= 3.1 and `bundle install`. Use `rails new` for a verified application
   - `none`: Minimal agent-only repo (`README.md` + `.gitignore`)
2. **Universal Agent Harness (Always Included)**:
   - `AGENTS.md`: Project overview, `$arch` rules, directory map (`$outputs_dir/`, `$scripts_dir/`, `$prompts_file`), and conditional `graphify` instructions (omitted when `--no-graphify` is set)
   - `graphify-out/`: Knowledge graph placeholder (`graphify-out/.gitkeep` unless `--no-graphify` is passed; only populated if the external `graphify` CLI is installed and `graphify update .` succeeds)
   - `.remember/`: Persistent agent memory (`MEMORY.md` & `decisions.md`, or copied from `~/.config/projboot/remember/`)
   - `.agents/skills/`: Reusable project skills (copied from `~/.config/projboot/skills/` or starter `project-conventions/SKILL.md`)
   - `$prompts_file` (default `PROMPTS.md`): Ordered prompt catalog
   - `$outputs_dir/` & `$scripts_dir/` directories
3. **Assistant Overlays (`-a / --agent`, repeatable)**:
   - `-a claude`: `CLAUDE.md` (project conventions and `@AGENTS.md` / `@.remember/MEMORY.md` references) + `.claude/settings.json` (minimal valid `{}` JSON settings file; project conventions live in `CLAUDE.md` and `AGENTS.md` rather than unsupported settings keys)
   - `-a gh-copilot`: `.github/copilot-instructions.md` + `.github/prompts/bootstrap.prompt.md`
   - `-a codeassistant`: `.codeassistant/instructions.md` (custom/legacy instruction-file adapter kept for compatibility; does not claim undocumented native client auto-loading)
   - `-a cursor`: `.cursor/rules/project.mdc` (YAML frontmatter with quoted `globs` and `alwaysApply: true`)
   - *Verification scope*: automated tests verify static format decoding (JSON and YAML frontmatter parsing) of generated overlay files; live native client behavior must be verified in the respective assistant client.

### Post-Generation Summary, First Steps & User-Run Checks

`projboot create` never installs dependencies, builds or runs generated code, or executes project test suites automatically. After writing the scaffold, it prints a summary separating:
- **Generated and configured files**: the selected `--lang` profile, composed harness paths, and assistant overlays.
- **Hook & remote status (actual results)**: whether `git init -b main` and `graphify update .` actually ran or remain `pending / not run` (missing tools or skipped hooks are never reported as success), and whether `--create` ran against GitHub.
- **First steps & user-runnable verification checks (not executed by `projboot`)**:
  - `python` / `python-microservice`:
    - Setup & run: `cd <name> && python -m venv .venv && source .venv/bin/activate && pip install -e . && appstarter` (or `python -m appstarter`)
    - User-run checks: `pip install pytest && pytest` and `pip install build && python -m build`
  - `typescript`:
    - Setup, build & run: `cd <name> && npm install && npm run build && npm start` (no test runner or `test` script is pre-configured in `package.json`)
  - `helm-chart`:
    - User-run checks: `cd <name> && helm lint . && helm template <name> .` (local chart validation only; cluster deployment is not configured and `ghcr.io/example/<name>` in `values.yaml` is a placeholder image)
  - `rails` (**experimental layout sketch only — not a runnable Rails app**):
    - User-run syntax check on generated files only: `cd <name> && ruby -c config/application.rb && ruby -c app/controllers/application_controller.rb` (use `rails new` with Ruby >= 3.1 for a runnable application)
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
- `~/.config/projboot/skills/` — Any skill files placed here are automatically copied into `.agents/skills/` and rendered with your project's `$name`, `$arch`, `$outputs_dir`, `$scripts_dir`, and `$prompts_file` variables.
- `~/.config/projboot/remember/` — Starter memory templates copied into `.remember/` on every new project.

Use a named preset with `-p / --preset`:

```bash
projboot create my-service -l python -p clean-arch
```

---

## Classic Template & Dirtree Commands

List available base templates:

```bash
projboot list-templates
```

Scaffold directly from a base template (without the AI agent harness):

```bash
projboot init --name my-svc --template python-microservice \
  --description "My service" --license mit --holder "Your Name" --local
```

Override or add template variables with `--var` (repeatable):

```bash
projboot init --name demo --template typescript --var name=real-package-name --local
```

Build a layout from a `tree`-style file — directories become paths, leaf files are materialized empty:

```bash
projboot init-from-tree --name myproject --tree-file examples/tree.txt --gitkeep --local
```

`--gitkeep` drops a `.gitkeep` in empty directories so they survive; `--force` allows merging into a non-empty local target. Generated files may replace files at matching paths; unrelated files are preserved.

---

## How Templating Works

Templates render with Python's `string.Template` (`$name`, `$description`, `$year`, `$holder`, `$arch`, `$outputs_dir`, `$scripts_dir`, `$prompts_file`, plus any `--var`). This is deliberate: Helm's Go-template syntax (`{{ .Values.foo }}`) and GitHub Actions expressions (`${{ secrets.X }}`) contain no bare `$identifier`, so they pass through untouched. `str.format()` or Jinja2 would corrupt them.

## Tests

```bash
pytest -q
```

The dirtree parser, template rendering, preset & user store loader, AI agent overlays, CLI (local + GitHub dispatch via mocks), and GitHub helper are all covered without any network access.
