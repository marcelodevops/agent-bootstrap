# project-bootstrapper

Scaffold projects from curated templates or a dirtree layout — to GitHub, or to
your local disk for fast iteration and offline testing.

## Install

```bash
pip install -e .            # installs the `project-bootstrapper` command
pip install -e ".[dev]"     # + pytest for the test suite
```

Requires Python 3.11+. The GitHub path needs `GITHUB_TOKEN` exported; the
`--local` path needs no token and no network.

## Templates

```bash
project-bootstrapper list-templates
```

| Template | What you get |
|---|---|
| `python-microservice` | src layout, Dockerfile, PyPI `pyproject.toml`, GitHub CI |
| `helm-chart` | `Chart.yaml`, `values.yaml`, deployment/service templates, `helm lint` CI |
| `typescript` | `package.json`, `tsconfig`, multi-stage Dockerfile |
| `rails` | minimal Rails-style skeleton (base layout, not full `rails new` output) |

## Usage

Create a repo and scaffold it on GitHub:

```bash
project-bootstrapper init --name my-svc --template python-microservice \
  --description "My service" --license mit --holder "Your Name"
```

Scaffold to the local disk instead (no token needed) — great for trying a
template before pushing:

```bash
project-bootstrapper init --name demo --template helm-chart --local
```

Override or add template variables with `--var` (repeatable):

```bash
project-bootstrapper init --name demo --template typescript \
  --var name=real-package-name --local
```

Build a layout from a `tree`-style file — directories become paths, leaf files
are materialized empty (git tracks directories implicitly via their files):

```bash
project-bootstrapper init-from-tree --name myproject --tree-file examples/tree.txt \
  --gitkeep --local
```

`--gitkeep` drops a `.gitkeep` in empty directories so they survive; `--force`
allows overwriting a non-empty `--local` target.

## How templating works

Templates render with Python's `string.Template` (`$name`, `$description`,
`$year`, `$holder`, plus any `--var`). This is deliberate: Helm's Go-template
syntax (`{{ .Values.foo }}`) and GitHub Actions expressions (`${{ secrets.X }}`)
contain no bare `$identifier`, so they pass through untouched. `str.format()` or
Jinja2 would corrupt them.

## Tests

```bash
pytest -q
```

The dirtree parser, template rendering, the CLI (local + GitHub dispatch, via
mocks), and the GitHub helper are all covered without any network access.
