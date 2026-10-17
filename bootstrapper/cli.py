"""Typer CLI for project-bootstrapper."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import typer

from . import dirtree
from .templates import LICENSES, get_template, render, template_names

app = typer.Typer(
    help="Scaffold projects from curated templates or a dirtree layout.",
    no_args_is_help=True,
)


def _parse_vars(pairs: list[str]) -> dict[str, str]:
    """Turn ``["k=v", ...]`` into a dict, splitting on the first ``=``."""
    out: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise typer.BadParameter(f"--var expects key=value, got {pair!r}")
        key, _, value = pair.partition("=")
        out[key.strip()] = value
    return out


def _variables(
    name: str, description: str, holder: str, extra: dict[str, str] | None = None
) -> dict[str, str]:
    variables = {
        "name": name,
        "description": description,
        "year": str(dt.date.today().year),
        "holder": holder or name,
    }
    variables.update(extra or {})  # user --var overrides built-ins
    return variables


def _license_text(license: str, variables: dict[str, str]) -> str | None:
    if license == "none":
        return None
    body = LICENSES.get(license)
    if body is None:
        typer.echo(f"Unknown license '{license}'. Skipping.")
        return None
    return render(body, **variables)


def _safe_join(base: Path, rel: str) -> Path:
    """Join ``rel`` onto ``base``, refusing empty paths or ones that escape it."""
    if not rel:
        raise ValueError("Refusing to write an empty path")
    candidate = (base / rel).resolve()
    root = base.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Refusing to write outside target dir: {rel!r}")
    return candidate


def _write_local(target: Path, files: dict[str, str], force: bool) -> None:
    if target.exists() and any(target.iterdir()) and not force:
        typer.echo(f"Refusing to overwrite non-empty dir {target}/ (use --force)", err=True)
        raise typer.Exit(code=1)
    for rel, content in files.items():
        path = _safe_join(target, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    typer.echo(f"Scaffolded {len(files)} file(s) into {target}/")


def _emit(
    files: dict[str, str],
    *,
    name: str,
    description: str,
    private: bool,
    org: str | None,
    local: bool,
    force: bool,
) -> None:
    """Write the scaffold to disk (--local) or push it to a new GitHub repo."""
    if local:
        _write_local(Path(name), files, force)
        return

    # Imported lazily so --local and tests never require PyGithub/network.
    from .github_utils import add_file, create_repo, get_github, get_owner

    gh = get_github()
    owner = get_owner(gh, org)
    repo = create_repo(owner, name, description, private)
    typer.echo(f"Repo ready: {repo.clone_url}")
    for path, content in files.items():
        add_file(repo, path, content, f"Add {path}")
        typer.echo(f"  + {path}")
    typer.echo("Done.")


def _build_template_files(
    template: str, variables: dict[str, str], license: str
) -> dict[str, str]:
    spec = get_template(template)
    files = {path: render(body, **variables) for path, body in spec["files"].items()}
    lic = _license_text(license, variables)
    if lic is not None:
        files["LICENSE"] = lic
    return files


def _tree_to_files(tree_file: Path, gitkeep: bool) -> dict[str, str]:
    """Materialize a dirtree layout as empty files (dirs are implicit in git)."""
    tree = dirtree.read_tree_file(tree_file)
    entries = dirtree.flatten(tree)
    root_name = next(iter(tree))
    root_prefix = f"{root_name}/"

    files: dict[str, str] = {}
    for e in entries:
        if not e.startswith(root_prefix) or e == root_prefix:
            continue
        rel = e[len(root_prefix) :]
        if not rel.endswith("/"):  # a file: touch it empty
            files[rel] = ""

    if gitkeep:
        for d in dirtree.empty_dirs(entries):
            if d == root_name or not d.startswith(root_prefix):
                continue
            rel_dir = d[len(root_prefix) :].rstrip("/")
            if rel_dir:
                files[f"{rel_dir}/.gitkeep"] = ""

    if not files:
        raise typer.BadParameter("tree produced no files")
    return files


@app.command("list-templates")
def list_templates() -> None:
    """Show available templates and their descriptions."""
    for name in template_names():
        typer.echo(f"  {name:24} {get_template(name)['description']}")


@app.command()
def init(
    name: str = typer.Option(..., help="Project/repository name"),
    template: str = typer.Option(
        "python-microservice", help="Template name (see list-templates)"
    ),
    description: str = typer.Option("", help="Short description"),
    private: bool = typer.Option(True, help="Make the repo private"),
    org: str | None = typer.Option(None, help="GitHub organization"),
    license: str = typer.Option("none", help="License: mit/apache2/gpl3/none"),
    holder: str = typer.Option("", help="Copyright holder for the license"),
    variable: list[str] = typer.Option(
        [], "--var", "-V", help="Extra template variable as key=value (repeatable)"
    ),
    local: bool = typer.Option(
        False, "--local", help="Write to ./<name>/ instead of GitHub"
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite a non-empty --local target dir"
    ),
) -> None:
    """Create a project scaffold from a curated template."""
    variables = _variables(name, description, holder, _parse_vars(variable))
    files = _build_template_files(template, variables, license)
    _emit(
        files,
        name=name,
        description=description,
        private=private,
        org=org,
        local=local,
        force=force,
    )


@app.command("init-from-tree")
def init_from_tree(
    name: str = typer.Option(..., help="Project/repository name"),
    tree_file: Path = typer.Option(
        ..., "--tree-file", exists=True, readable=True, help="Path to dirtree file"
    ),
    description: str = typer.Option("", help="Short description"),
    private: bool = typer.Option(True, help="Make the repo private"),
    org: str | None = typer.Option(None, help="GitHub organization"),
    gitkeep: bool = typer.Option(
        False, help="Add .gitkeep so empty directories survive"
    ),
    local: bool = typer.Option(
        False, "--local", help="Write to ./<name>/ instead of GitHub"
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite a non-empty --local target dir"
    ),
) -> None:
    """Create a project scaffold from a dirtree layout file."""
    files = _tree_to_files(tree_file, gitkeep)
    _emit(
        files,
        name=name,
        description=description,
        private=private,
        org=org,
        local=local,
        force=force,
    )


if __name__ == "__main__":
    app()
