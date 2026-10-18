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

## Quickstart: AI Agent Project Bootstrapping (`projboot create`)

### 1. Initialize your personal `~/.config/projboot/` presets & skills store
```bash
projboot config-init
projboot list-presets
```

### 2. Create a local AI-agent Python project with Claude + GitHub Copilot + custom folders
```bash
projboot create demo-agent \
  -l python \
  -a claude -a gh-copilot \
  --arch hexagonal \
  --outputs-dir artifacts/out \
  --scripts-dir hack \
  --prompts-file PROMPTS.md
```

### 3. Create locally AND push to a new GitHub repo (requires `GITHUB_TOKEN`)
```bash
projboot create new-project -l python -a claude -a gh-copilot -r github --create --clone
```

### Example Generated Project Layout

```text
demo-agent/
├── AGENTS.md                                    # Universal instructions + Graphify rules + layout map
├── CLAUDE.md                                    # Claude Code instructions (-a claude)
├── PROMPTS.md                                   # Ordered prompts catalog (--prompts-file)
├── .claude/
│   └── settings.json                            # Claude Code project settings (-a claude)
├── .github/
│   ├── copilot-instructions.md                  # GitHub Copilot instructions (-a gh-copilot)
│   ├── prompts/bootstrap.prompt.md              # Copilot reusable prompt (-a gh-copilot)
│   └── workflows/ci.yml                         # Base language CI (-l python)
├── .agents/
│   └── skills/project-conventions/SKILL.md      # Project skills (from ~/.config/projboot/skills/)
├── .remember/
│   ├── MEMORY.md                                # Persistent agent memory
│   └── decisions.md                             # Architectural decisions log
├── graphify-out/                                # Knowledge graph (auto-updated via `graphify update .`)
├── artifacts/out/                               # Custom outputs folder (--outputs-dir)
├── hack/                                        # Custom scripts folder (--scripts-dir)
├── pyproject.toml
├── Dockerfile
└── src/
    └── main.py
```

### `projboot create` Options

| Flag | Default | Description |
|---|---|---|
| `<name>` | *(required)* | Target directory and repository name |
| `-l`, `--lang` | `python` | Base template: `python`, `python-microservice`, `typescript`, `rails`, `helm-chart`, `none` |
| `-a`, `--agent` | *(from preset)* | Repeatable assistant overlay: `claude`, `gh-copilot`, `codeassistant`, `cursor` |
| `-p`, `--preset` | `default` | Workflow preset name from `~/.config/projboot/presets.toml` (see `projboot list-presets`) |
| `--arch` | `modular` | Architecture style wired into agent instructions |
| `--outputs-dir` | `outputs` | Directory created and wired for generated artifacts/outputs |
| `--scripts-dir` | `scripts` | Directory created and wired for helper/automation scripts |
| `--prompts-file` | `PROMPTS.md` | File created and wired for ordered project prompts |
| `-r`, `--remote` | `None` | Remote provider (`github` / `gh`) |
| `--create` | `False` | Create the remote repository on GitHub and push all scaffolded files |
| `--clone` | `False` | Keep local working directory initialized alongside remote creation |
| `--license` | `none` | License: `mit`, `apache2`, `gpl3`, `none` |
| `--holder` | `<name>` | Copyright holder for `LICENSE` |
| `-V`, `--var` | `[]` | Extra template variable as `key=value` (repeatable) |
| `--no-git` | `False` | Skip running `git init -b main` locally |
| `--no-graphify` | `False` | Skip running `graphify update .` locally |
| `--force` | `False` | Overwrite a non-empty local target directory |

### What `projboot create` Generates

1. **Base Language Stack (`-l / --lang`)**:
   - `python` / `python-microservice`: `src/` layout, `pyproject.toml`, `Dockerfile`, GitHub CI
   - `typescript`: `package.json`, `tsconfig.json`, `src/index.ts`, multi-stage `Dockerfile`
   - `helm-chart`: `Chart.yaml`, `values.yaml`, `templates/`, `helm lint` CI
   - `rails`: Minimal Rails skeleton
   - `none`: Minimal agent-only repo (`README.md` + `.gitignore`)
2. **Universal Agent Harness (Always Included)**:
   - `AGENTS.md`: Project overview, `$arch` rules, directory map (`$outputs_dir/`, `$scripts_dir/`, `$prompts_file`), and `graphify` instructions
   - `graphify-out/`: Knowledge graph folder (automatically updated via `graphify update .` if `graphify` is installed)
   - `.remember/`: Persistent agent memory (`MEMORY.md` & `decisions.md`, or copied from `~/.config/projboot/remember/`)
   - `.agents/skills/`: Reusable project skills (copied from `~/.config/projboot/skills/` or starter `project-conventions/SKILL.md`)
   - `$prompts_file` (default `PROMPTS.md`): Ordered prompt catalog
   - `$outputs_dir/` & `$scripts_dir/` directories
3. **Assistant Overlays (`-a / --agent`, repeatable)**:
   - `-a claude`: `CLAUDE.md` + `.claude/settings.json`
   - `-a gh-copilot`: `.github/copilot-instructions.md` + `.github/prompts/bootstrap.prompt.md`
   - `-a codeassistant`: `.codeassistant/instructions.md`
   - `-a cursor`: `.cursor/rules/project.mdc`

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

`--gitkeep` drops a `.gitkeep` in empty directories so they survive; `--force` allows overwriting a non-empty local target directory.

---

## How Templating Works

Templates render with Python's `string.Template` (`$name`, `$description`, `$year`, `$holder`, `$arch`, `$outputs_dir`, `$scripts_dir`, `$prompts_file`, plus any `--var`). This is deliberate: Helm's Go-template syntax (`{{ .Values.foo }}`) and GitHub Actions expressions (`${{ secrets.X }}`) contain no bare `$identifier`, so they pass through untouched. `str.format()` or Jinja2 would corrupt them.

## Tests

```bash
pytest -q
```

The dirtree parser, template rendering, preset & user store loader, AI agent overlays, CLI (local + GitHub dispatch via mocks), and GitHub helper are all covered without any network access.
