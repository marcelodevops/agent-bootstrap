# agent-bootstrap (`projboot`)

[![PyPI](https://img.shields.io/pypi/v/agent-bootstrap)](https://pypi.org/project/agent-bootstrap/)
[![Python](https://img.shields.io/pypi/pyversions/agent-bootstrap)](https://pypi.org/project/agent-bootstrap/)

Scaffold AI-agent-ready projects from curated language templates, customizable workflow presets, or a `tree`-style layout — locally first, with one-command GitHub repository creation.

## Install

```bash
pip install agent-bootstrap          # installs both `projboot` and `agent-bootstrap`
pip install -e ".[dev]"              # dev: + pytest for the test suite
```

Requires Python 3.11+. Local scaffolding needs no token and no network; GitHub remote creation (`-r github --create`) uses `GITHUB_TOKEN`.

---

## Quickstart: AI Agent Project Bootstrapping (`projboot create`)

Create a new Python project pre-wired for **Claude Code** and **GitHub Copilot**, scaffolded locally and pushed to a new GitHub repository:

```bash
projboot create new-project -l python -a claude -a gh-copilot -r github --create --clone
```

Or scaffold locally with custom directories for generated outputs, helper scripts, an ordered prompts catalog, and architecture conventions (all automatically wired into `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, etc.):

```bash
projboot create new-project \
  -l python \
  -a claude -a gh-copilot -a codeassistant \
  --arch hexagonal \
  --outputs-dir artifacts/out \
  --scripts-dir hack \
  --prompts-file docs/PROMPTS.md
```

### What `projboot create` Generates

1. **Base Language Stack (`-l / --lang`)**:
   - `python` / `python-microservice`: installable **starter** (not a production microservice) — `src/appstarter/` package with both documented run paths (the `appstarter` console script and `python -m appstarter`), `tests/`, `pyproject.toml`, `Dockerfile`, GitHub CI running `pytest` + `python -m build`. The import package is deliberately named `appstarter` regardless of the project name, so hyphenated identities like `my-app` still yield a stable `import appstarter`
   - `typescript`: `package.json`, `tsconfig.json`, `src/index.ts`, multi-stage `Dockerfile`
   - `helm-chart`: `Chart.yaml`, `values.yaml`, `templates/`, `helm lint` CI
   - `rails`: **EXPERIMENTAL layout only — not a runnable Rails app.** A partial sketch (`Gemfile`, `config.ru`, `config/application.rb`, one controller); `config/environment.rb`, `config/boot.rb`, `config/routes.rb`, `bin/rails`, `Rakefile`, `app/views/` and `db/` are absent, and `rails` `~> 7.1` additionally needs Ruby >= 3.1 and `bundle install`. Use `rails new` for a verified application
   - `none`: Minimal agent-only repo (`README.md` + `.gitignore`)
2. **Universal Agent Harness (Always Included)**:
   - `AGENTS.md`: Project overview, `$arch` rules, directory map (`$outputs_dir/`, `$scripts_dir/`, `$prompts_file`), and `graphify` instructions
   - `graphify-out/`: Knowledge graph folder (automatically updated via `graphify update .` if `graphify` is installed)
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

---

## Presets & Personal User Store (`~/.config/projboot/`)

Initialize your personal `projboot` configuration directory (or set `PROJBOOT_HOME` to customize its path):

```bash
projboot config-init
projboot list-presets
```

This creates:
- `~/.config/projboot/presets.toml` — Define named presets (`default`, `clean-arch`, or your own) with default `arch`, `outputs_dir`, `scripts_dir`, `prompts_file`, and `agents`.
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

`--gitkeep` drops a `.gitkeep` in empty directories so they survive; `--force` allows overwriting a non-empty local target directory.

---

## How Templating Works

Templates render with Python's `string.Template` (`$name`, `$description`, `$year`, `$holder`, `$arch`, `$outputs_dir`, `$scripts_dir`, `$prompts_file`, plus any `--var`). This is deliberate: Helm's Go-template syntax (`{{ .Values.foo }}`) and GitHub Actions expressions (`${{ secrets.X }}`) contain no bare `$identifier`, so they pass through untouched. `str.format()` or Jinja2 would corrupt them.

## Tests

```bash
pytest -q
```

The dirtree parser, template rendering, preset & user store loader, AI agent overlays, CLI (local + GitHub dispatch via mocks), and GitHub helper are all covered without any network access.
