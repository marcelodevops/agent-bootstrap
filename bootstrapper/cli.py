"""Typer CLI for project-bootstrapper (and projboot)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import typer

from . import dirtree
from .agents import SUPPORTED_AGENTS
from .composer import compose_project_files, run_post_hooks
from .presets import (
    get_config_dir,
    init_config_dir,
    load_presets,
    resolve_preset,
)
from .templates import LICENSES, get_template, render, template_names

app = typer.Typer(
    help="Scaffold projects and AI agent harnesses from curated templates, presets, or dirtrees.",
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
    # Validate every path first so an escaping/empty path aborts before any
    # file is written, instead of leaving a half-generated project behind.
    try:
        planned = [(content, _safe_join(target, rel)) for rel, content in files.items()]
    except ValueError as exc:
        typer.echo(f"Invalid output path: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    for content, path in planned:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    typer.echo(f"Scaffolded {len(files)} file(s) into {target}/")


def _push_github(
    files: dict[str, str],
    *,
    name: str,
    description: str,
    private: bool,
    org: str | None,
    force: bool,
) -> str:
    """Create a GitHub repository and upload all scaffolded files.

    Returns the repo's clone URL so callers can wire a local checkout.
    """
    # Imported lazily so --local and tests never require PyGithub/network.
    from .github_utils import (
        RepoExistsError,
        add_file,
        create_repo,
        get_github,
        get_owner,
    )

    gh = get_github()
    owner = get_owner(gh, org)
    try:
        repo = create_repo(owner, name, description, private, force=force)
    except RepoExistsError as exc:
        typer.echo(
            f"Repo {exc.full_name} already exists; refusing to overwrite its files "
            "(pass --force to update them).",
            err=True,
        )
        raise typer.Exit(code=1) from exc
    typer.echo(f"Repo ready: {repo.clone_url}")
    for path, content in files.items():
        add_file(repo, path, content, f"Add {path}")
        typer.echo(f"  + {path}")
    typer.echo("Done.")
    return repo.clone_url


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
    _push_github(
        files,
        name=name,
        description=description,
        private=private,
        org=org,
        force=force,
    )


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


@app.command("list-presets")
def list_presets_cmd() -> None:
    """Show available workflow presets (built-in + ~/.config/projboot/presets.toml)."""
    presets = load_presets()
    for name in sorted(presets):
        p = presets[name]
        agents_str = ", ".join(p.agents) if p.agents else "none"
        typer.echo(
            f"  {name:16} arch={p.arch} outputs={p.outputs_dir}/ "
            f"scripts={p.scripts_dir}/ prompts={p.prompts_file} agents=[{agents_str}]"
        )


@app.command("config-init")
def config_init(
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing files in ~/.config/projboot/"
    ),
) -> None:
    """Materialize starter presets.toml, skills/, and remember/ in ~/.config/projboot/."""
    target_dir = get_config_dir()
    written = init_config_dir(target_dir, force=force)
    typer.echo(f"Initialized {len(written)} file(s) in {target_dir}/")


@app.command()
def create(
    name: str = typer.Argument(..., help="Project/repository name"),
    lang: str = typer.Option(
        "python",
        "--lang",
        "-l",
        help="Language/base template (python, python-microservice, typescript, rails, helm-chart, none)",
    ),
    agent: list[str] = typer.Option(
        [],
        "--agent",
        "-a",
        help=f"AI assistant overlay (repeatable): {', '.join(SUPPORTED_AGENTS)}",
    ),
    preset: str = typer.Option(
        "default",
        "--preset",
        "-p",
        help="Workflow preset name (see list-presets)",
    ),
    arch: str | None = typer.Option(
        None, "--arch", help="Override architecture style in agent instructions"
    ),
    outputs_dir: str | None = typer.Option(
        None, "--outputs-dir", help="Override directory for generated outputs"
    ),
    scripts_dir: str | None = typer.Option(
        None, "--scripts-dir", help="Override directory for helper scripts"
    ),
    prompts_file: str | None = typer.Option(
        None, "--prompts-file", help="Override ordered prompts catalog file path"
    ),
    remote: str | None = typer.Option(
        None, "--remote", "-r", help="Remote provider (e.g. 'github')"
    ),
    create_remote: bool = typer.Option(
        False, "--create", help="Create the repository on the remote provider"
    ),
    clone: bool = typer.Option(
        False, "--clone", help="Keep local working directory initialized alongside remote creation"
    ),
    description: str = typer.Option("", help="Short project description"),
    private: bool = typer.Option(True, help="Make the remote repository private"),
    org: str | None = typer.Option(None, help="GitHub organization"),
    license: str = typer.Option("none", help="License: mit/apache2/gpl3/none"),
    holder: str = typer.Option("", help="Copyright holder for the license"),
    variable: list[str] = typer.Option(
        [], "--var", "-V", help="Extra template variable as key=value (repeatable)"
    ),
    no_git: bool = typer.Option(
        False, "--no-git", help="Skip running `git init` locally"
    ),
    no_graphify: bool = typer.Option(
        False, "--no-graphify", help="Skip running `graphify update .` locally"
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite a non-empty local target directory"
    ),
) -> None:
    """Create an AI-agent-enabled project with universal harness, presets, and assistant overlays."""
    if remote is not None and remote.lower() not in ("github", "gh"):
        raise typer.BadParameter(f"Unsupported remote {remote!r}. Supported: github")

    try:
        resolved_preset = resolve_preset(
            preset,
            arch=arch,
            outputs_dir=outputs_dir,
            scripts_dir=scripts_dir,
            prompts_file=prompts_file,
            agents=agent,
        )
        files = compose_project_files(
            name=name,
            description=description,
            lang=lang,
            preset=resolved_preset,
            license=license,
            holder=holder,
            extra_vars=_parse_vars(variable),
            include_graphify=not no_graphify,
        )
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    target = Path(name)
    _write_local(target, files, force)

    # Upload only when --create is given; --remote just names the provider
    # (defaulting to github), so the two flags no longer overlap silently.
    clone_url: str | None = None
    if create_remote:
        if remote is None:
            typer.echo("No --remote provider given; defaulting to github.")
        clone_url = _push_github(
            files,
            name=name,
            description=description,
            private=private,
            org=org,
            force=force,
        )
    elif remote:
        typer.echo(f"Remote '{remote}' selected but --create not given; not uploading.")

    # --clone should leave a checkout connected to the remote: configure origin
    # and make an initial commit. This needs git, so it's skipped under --no-git.
    connect_url = clone_url if clone else None
    if clone and no_git:
        typer.echo("Note: --clone needs git but --no-git was set; repo not connected.")
        connect_url = None

    for msg in run_post_hooks(
        target,
        init_git=not no_git,
        run_graphify=not no_graphify,
        connect_remote_url=connect_url,
        make_commit=bool(connect_url),
    ):
        typer.echo(f"  * {msg}")

    if connect_url:
        typer.echo(
            "Local repo has origin + an initial commit; files were uploaded via the "
            "API, so `git fetch` and reconcile before `git push`."
        )


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
