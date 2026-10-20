"""Typer CLI for project-bootstrapper (and projboot)."""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath

import typer

from . import dirtree
from .agents import SUPPORTED_AGENTS
from .composer import (
    PathCollisionError,
    compose_project_files,
    find_output_conflicts,
    run_post_hooks,
)
from .presets import (
    PresetConfig,
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

# A project name is used directly as the local directory and as a package /
# repository identity, so it must be one safe path segment free of separators,
# whitespace, quotes and control characters. Conservative shared contract: start
# with a letter or digit, then letters, digits, dot, hyphen, underscore (or
# accented letters); no length games beyond 100. This rejects ``../evil``,
# ``/etc/passwd``, ``sub/out``, ``foo bar``, ``foo\nbar`` and ``-lead`` while
# accepting ``demo``, ``new-project``, ``my_app``, ``core.v2`` and ``café``.
# ``\Z`` rather than ``$`` is required: ``$`` also matches the position before a
# terminal newline, which would let ``demo\n`` through and scaffold into a
# newline-named directory. ``fullmatch`` also refuses acceptance on a prefix.
_NAME_RE = re.compile(r"[A-Za-z0-9\u00C0-\u024F][A-Za-z0-9._\u00C0-\u024F-]{0,99}\Z")

# Prefix for the temporary sibling directory a new project is staged in before
# it is renamed into place (see _write_local).
_TMP_PREFIX = ".projboot-staging-"


def _validate_name(name: str) -> None:
    """Reject identities that are not a single safe package/repo segment."""
    if name in (".", ".."):
        raise typer.BadParameter("project name must not be '.' or '..'")
    if _NAME_RE.fullmatch(name):
        return
    raise typer.BadParameter(
        f"invalid project name {name!r}: use a package/repository identity "
        "(letters, digits, dot, hyphen, underscore; must start with a letter or "
        "digit; no path separators, spaces, quotes or control characters)"
    )


def _reject_contradictory_options(
    *, clone: bool, create_remote: bool, no_git: bool
) -> None:
    """Refuse plainly incompatible flag combinations before any local write.

    ``--clone`` means "leave a working checkout connected to the created remote",
    so it needs ``--create`` (a remote to connect to) and needs git (so
    ``--no-git`` contradicts it). ``--remote`` without ``--create`` stays the
    existing informational "not uploading" behavior and is NOT rejected here.
    """
    if clone and not create_remote:
        raise typer.BadParameter(
            "--clone requires --create: there is no remote repository to connect "
            "the local checkout to"
        )
    if clone and no_git:
        raise typer.BadParameter(
            "--clone needs git but --no-git was set; drop --no-git to get a "
            "connected checkout, or drop --clone to scaffold without one"
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


def _reject_resolved_collisions(
    planned: list[tuple[str, str, Path]], root: Path
) -> None:
    """Refuse a write plan whose *resolved* destinations collide.

    ``find_output_conflicts`` normalizes lexically (``PurePosixPath``) and so
    cannot see two things that only unify once a path is resolved against the
    filesystem:

    * a ``..`` traversal alias — ``dir/../README.md`` and ``README.md`` resolve
      to one file, so the last write would silently win;
    * an in-root symlink alias — ``alias/file.txt`` (``alias -> real``) and
      ``real/file.txt`` resolve to the same file.

    It also re-checks file/ancestor conflicts on resolved paths. Runs before the
    first ``mkdir``/``write_text``. Containment (escaping the target) is still
    enforced by ``_safe_join``.
    """
    owners: dict[Path, tuple[str, str]] = {}  # resolved dest -> (rel, content)
    for rel, content, path in planned:
        prev = owners.get(path)
        if prev is not None and prev[1] != content:
            raise PathCollisionError(
                f"'{prev[0]}' and '{rel}' resolve to the same output "
                f"{_display(path, root)!r} through a '..' traversal or a symlink; "
                "refusing to overwrite one with the other"
            )
        owners.setdefault(path, (rel, content))

    destinations = set(owners)
    for path, (rel, _content) in owners.items():
        for ancestor in path.parents:
            if ancestor in destinations:
                other = owners[ancestor][0]
                raise PathCollisionError(
                    f"'{other}' resolves to a file that is also the parent "
                    f"directory of '{rel}' ({_display(path, root)!r}); refusing to "
                    "create a conflicting path"
                )


def _display(path: Path, root: Path) -> str:
    """Render a resolved destination relative to the target root for messages."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _force_remove(func, path, _exc) -> None:  # pragma: no cover - cleanup safety net
    """shutil.rmtree onerror: make a read-only entry removable, then retry once."""
    try:
        os.chmod(path, 0o700)
        func(path)
    except OSError:
        pass


def _reject_existing_fs_conflicts(rroot: Path, planned: list[tuple[str, str, Path]]) -> None:
    """Refuse a --force merge whose plan fights the *on-disk* filesystem.

    When the target already exists (forced overwrite), a planned file whose name
    is currently a directory, or a planned nested path whose ancestor is
    currently a file, would crash ``mkdir``/``write_text`` half-way and leave a
    partially written target. Detecting it up front lets the pre-existing tree
    survive untouched. This is filesystem-state aware, unlike the plan-only
    ``find_output_conflicts`` and ``_reject_resolved_collisions`` checks.
    """
    for rel, _content, path in planned:
        try:
            relative = path.relative_to(rroot)
        except ValueError:  # outside the target: already refused by _safe_join
            continue
        parts = relative.parts
        for i in range(len(parts) - 1):  # every ancestor segment must be a dir
            ancestor = rroot.joinpath(*parts[: i + 1])
            if ancestor.exists() and not ancestor.is_dir():
                raise PathCollisionError(
                    f"existing {_display(ancestor, rroot)!r} is a file but the "
                    f"plan needs it to be a directory for '{rel}'"
                )
        final = rroot.joinpath(*parts)  # the file itself must not be a live dir
        if final.is_dir():
            raise PathCollisionError(
                f"existing {_display(final, rroot)!r} is a directory but the "
                f"plan writes a file at '{rel}'"
            )


def _is_nonempty_dir(target: Path) -> bool:
    return target.is_dir() and any(target.iterdir())


def _validate_write_plan(
    target: Path, files: dict[str, str], force: bool
) -> tuple[list[tuple[str, str, Path]], bool]:
    """Run every read-only check generation performs before its first write.

    Returns the planned ``(rel, content, resolved destination)`` triples plus
    the non-empty snapshot taken at preflight, so the caller's write-path choice
    stays tied to this single observation rather than a second one. Exits
    exactly like ``_write_local`` on refusal or collisions. It only reads
    (``resolve``/``exists``/``iterdir``), so ``preview`` can reuse it to fail on
    the same invalid inputs and output collisions as ``create``.
    """
    nonempty_existing = _is_nonempty_dir(target)
    if nonempty_existing and not force:
        typer.echo(f"Refusing to overwrite non-empty dir {target}/ (use --force)", err=True)
        raise typer.Exit(code=1)

    rroot = target.resolve()
    # Validate the whole plan before any write. Three layers, cheapest first:
    # lexical composition collisions, resolved-destination aliases/symlinks (the
    # accepted A1 guards), and, only for a forced merge, on-disk type conflicts.
    try:
        find_output_conflicts(files)
        planned = [(rel, content, _safe_join(target, rel)) for rel, content in files.items()]
        _reject_resolved_collisions(planned, rroot)
        if target.exists() and not target.is_dir():
            raise PathCollisionError(f"target {_display(rroot, rroot)!r} exists and is not a directory")
        if nonempty_existing:
            _reject_existing_fs_conflicts(rroot, planned)
    except ValueError as exc:
        typer.echo(f"Invalid output path: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    return planned, nonempty_existing


def _write_local(target: Path, files: dict[str, str], force: bool) -> None:
    planned, nonempty_existing = _validate_write_plan(target, files, force)
    if nonempty_existing:
        # Forced merge into an existing tree: unrelated files must survive, so an
        # atomic whole-directory swap is impossible. Write in place after the
        # preflight above; on a late disk error leave the target as-is (no atomic
        # publish is promised for existing directories).
        try:
            for _rel, content, path in planned:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
        except OSError as exc:
            typer.echo(f"Failed to write into {target}/: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo(f"Scaffolded {len(files)} file(s) into {target}/")
        return

    # New (or empty) target: stage the complete scaffold in a temporary sibling
    # and rename it into place only after every file is written. A failure partway
    # removes just our staging directory and leaves the requested target absent.
    rroot = target.resolve()
    parent = rroot.parent if rroot.parent != rroot else Path.cwd()
    staging = Path(tempfile.mkdtemp(prefix=f"{_TMP_PREFIX}{rroot.name}.", dir=parent))
    try:
        for rel, content, path in planned:
            dest = staging / path.relative_to(rroot)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content)
        staging.replace(rroot)
    except OSError as exc:
        shutil.rmtree(staging, onerror=_force_remove)
        typer.echo(
            f"Failed to scaffold {target}/: {exc}; target left unchanged", err=True
        )
        raise typer.Exit(code=1) from exc
    typer.echo(f"Scaffolded {len(files)} file(s) into {target}/")


def _push_github(
    *,
    name: str,
    description: str,
    private: bool,
    org: str | None,
    force: bool,
) -> str:
    """Create or select a GitHub repository without changing its contents.

    Returns the repo's clone URL so callers can wire a local checkout.
    """
    # Imported lazily so --local and tests never require PyGithub/network.
    from .github_utils import (
        RepoExistsError,
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
            f"Repo {exc.full_name} already exists; refusing to use it without --force.",
            err=True,
        )
        raise typer.Exit(code=1) from exc
    typer.echo(f"Using GitHub repository: {repo.clone_url}")
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
    """Write locally, or push a temporary checkout to a GitHub repository."""
    if local:
        _write_local(Path(name), files, force)
        return
    clone_url = _push_github(
        name=name,
        description=description,
        private=private,
        org=org,
        force=force,
    )
    with tempfile.TemporaryDirectory(prefix="projboot-init-") as staging:
        target = Path(staging) / name
        _write_local(target, files, force=False)
        messages = run_post_hooks(
            target,
            init_git=True,
            run_graphify=False,
            connect_remote_url=clone_url,
            make_commit=True,
            stage_paths=list(files),
        )
    if not all(
        required in messages
        for required in (
            "Initialized git repository (main)",
            "Created initial commit",
            "Pushed initial commit to origin (main)",
        )
    ) or not any("origin remote:" in message for message in messages):
        for message in messages:
            typer.echo(f"  * {message}")
        typer.echo(
            f"Remote repository {clone_url} exists, but the scaffold push did not complete.",
            err=True,
        )
        raise typer.Exit(code=1)
    typer.echo(f"Pushed scaffold to {clone_url} with one Git history.")


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


def _resolve_options_and_compose(
    *,
    lang: str,
    agent: list[str],
    preset: str,
    arch: str | None,
    outputs_dir: str | None,
    scripts_dir: str | None,
    prompts_file: str | None,
    name: str,
    description: str,
    license: str,
    holder: str,
    variable: list[str],
    no_graphify: bool,
) -> tuple[PresetConfig, dict[str, str]]:
    """Resolve preset options and compose the full file plan, or refuse.

    ``create`` and ``preview`` both call this, so a preview is built from the
    exact same resolved options and composition result as generation.
    """
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
    return resolved_preset, files


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
        False,
        "--force",
        help="Merge into a non-empty local target or use an existing remote; pushes never rewrite remote history",
    ),
) -> None:
    """Create an AI-agent-enabled project with universal harness, presets, and assistant overlays."""
    _validate_name(name)
    _reject_contradictory_options(
        clone=clone, create_remote=create_remote, no_git=no_git
    )

    if remote is not None and remote.lower() not in ("github", "gh"):
        raise typer.BadParameter(f"Unsupported remote {remote!r}. Supported: github")

    resolved_preset, files = _resolve_options_and_compose(
        lang=lang,
        agent=agent,
        preset=preset,
        arch=arch,
        outputs_dir=outputs_dir,
        scripts_dir=scripts_dir,
        prompts_file=prompts_file,
        name=name,
        description=description,
        license=license,
        holder=holder,
        variable=variable,
        no_graphify=no_graphify,
    )

    target = Path(name)
    _validate_write_plan(target, files, force)

    # --remote only names the provider. --create makes the remote and, unless
    # --no-git was selected, pushes the generated scaffold with normal Git.
    clone_url: str | None = None
    if create_remote:
        if remote is None:
            typer.echo("No --remote provider given; defaulting to github.")
        clone_url = _push_github(
            name=name,
            description=description,
            private=private,
            org=org,
            force=force,
        )
    elif remote:
        typer.echo(f"Remote '{remote}' selected but --create not given; not uploading.")

    _write_local(target, files, force)

    # --clone remains a compatibility alias; all Git-enabled remote creates
    # connect origin and push the same initial history.
    connect_url = clone_url if (clone_url and not no_git) else None

    hook_messages = run_post_hooks(
        target,
        init_git=not no_git,
        run_graphify=not no_graphify,
        connect_remote_url=connect_url,
        make_commit=bool(connect_url),
        stage_paths=list(files),
    )
    for msg in hook_messages:
        typer.echo(f"  * {msg}")

    clone_ready = (
        any("origin remote:" in msg for msg in hook_messages)
        and "Created initial commit" in hook_messages
        and "Pushed initial commit to origin (main)" in hook_messages
    )

    _echo_create_summary(
        name=name,
        lang=lang,
        files=files,
        preset=resolved_preset,
        remote=remote,
        create_remote=create_remote,
        clone=clone,
        clone_url=clone_url,
        no_git=no_git,
        no_graphify=no_graphify,
        hook_messages=hook_messages,
    )
    if create_remote and not no_git and not clone_ready:
        raise typer.Exit(code=1)


_AGENT_OVERLAY_EXPECTED_PATHS: dict[str, tuple[str, ...]] = {
    "claude": ("CLAUDE.md", ".claude/settings.json"),
    "gh-copilot": (".github/copilot-instructions.md", ".github/prompts/bootstrap.prompt.md"),
    "codeassistant": (".codeassistant/instructions.md",),
    "cursor": (".cursor/rules/project.mdc",),
}


def _echo_create_summary(
    *,
    name: str,
    lang: str,
    files: dict[str, str],
    preset: PresetConfig,
    remote: str | None,
    create_remote: bool,
    clone: bool,
    clone_url: str | None,
    no_git: bool,
    no_graphify: bool,
    hook_messages: list[str],
) -> None:
    """Print post-generation status, user-runnable first steps, and verification checks.

    Separates what was written/configured on disk, what local/remote hooks
    actually ran, what commands are next steps for the user, and what remains
    unverified. Commands are derived from the composed ``files`` so tools or
    scripts absent from the scaffold are never suggested.
    """
    has_python = "pyproject.toml" in files and "src/appstarter/main.py" in files
    has_typescript = "package.json" in files and "tsconfig.json" in files
    has_helm = "Chart.yaml" in files
    has_rails = "Gemfile" in files and "config/application.rb" in files
    has_graphify = not no_graphify and "graphify-out/.gitkeep" in files

    git_ran_msg = next(
        (m for m in hook_messages if m.startswith("Initialized git repository")), None
    )
    git_skip_msg = next(
        (m for m in hook_messages if m.startswith("Skipped git init")), None
    )
    graphify_ran_msg = next(
        (
            m
            for m in hook_messages
            if m.startswith("Initialized graphify knowledge graph")
        ),
        None,
    )
    graphify_skip_msg = next(
        (m for m in hook_messages if m.startswith("Skipped graphify update")), None
    )
    origin_msg = next((m for m in hook_messages if "origin remote:" in m), None)
    commit_msg = next(
        (m for m in hook_messages if m == "Created initial commit"), None
    )
    push_msg = next(
        (m for m in hook_messages if m == "Pushed initial commit to origin (main)"),
        None,
    )

    typer.echo("")
    typer.echo(f"Generated and configured in {name}/:")
    if has_python:
        typer.echo(
            f"  profile (--lang): {lang} (Python starter package in src/appstarter/; "
            "starter point, not a production service)"
        )
    elif has_typescript:
        typer.echo(
            f"  profile (--lang): {lang} (TypeScript Node.js starter with src/index.ts "
            "and tsconfig.json)"
        )
    elif has_helm:
        typer.echo(
            f"  profile (--lang): {lang} (Helm chart scaffold with Chart.yaml, "
            "values.yaml, and templates/)"
        )
    elif has_rails:
        typer.echo(
            f"  profile (--lang): {lang} (EXPERIMENTAL layout sketch only — NOT a "
            "runnable Rails app)"
        )
    else:
        typer.echo(
            f"  profile (--lang): {lang} (minimal agent-only repository; no language "
            "runtime or build toolchain)"
        )

    harness_items: list[str] = []
    if "AGENTS.md" in files:
        harness_items.append("AGENTS.md")
    if preset.prompts_file in files:
        harness_items.append(preset.prompts_file)
    if any(p.startswith(f"{preset.outputs_dir}/") for p in files):
        harness_items.append(f"{preset.outputs_dir}/")
    if any(p.startswith(f"{preset.scripts_dir}/") for p in files):
        harness_items.append(f"{preset.scripts_dir}/")
    if any(p.startswith(".remember/") for p in files):
        harness_items.append(".remember/")
    if any(p.startswith(".agents/skills/") for p in files):
        harness_items.append(".agents/skills/")
    if has_graphify:
        harness_items.append("graphify-out/.gitkeep (Graphify placeholder only)")
    else:
        harness_items.append("Graphify integration not selected (--no-graphify)")
    typer.echo(f"  shared harness: {', '.join(harness_items)}")

    if preset.agents:
        overlay_parts: list[str] = []
        for agent_name in preset.agents:
            key = agent_name.strip().lower()
            expected = _AGENT_OVERLAY_EXPECTED_PATHS.get(key, ())
            present = [p for p in expected if p in files]
            if present:
                overlay_parts.append(f"{key} ({', '.join(present)})")
            else:
                overlay_parts.append(key)
        typer.echo(
            f"  assistant overlays: {', '.join(overlay_parts)} — static files written; "
            "live assistant client loading not verified"
        )
    else:
        typer.echo(
            "  assistant overlays: none selected (-a/--agent not set; shared "
            "AGENTS.md harness only)"
        )

    typer.echo("Hook & remote status (actual results):")
    if no_git:
        typer.echo("  git init: not run (--no-git)")
    elif git_ran_msg:
        typer.echo(f"  git init: ran — {git_ran_msg}")
    elif git_skip_msg:
        typer.echo(f"  git init: pending / not run — {git_skip_msg}")
    else:
        typer.echo("  git init: pending / not run — git init did not report completion")

    if no_graphify:
        typer.echo("  graphify update .: not selected (--no-graphify)")
    elif graphify_ran_msg:
        typer.echo(f"  graphify update .: ran — {graphify_ran_msg}")
    elif graphify_skip_msg:
        typer.echo(f"  graphify update .: pending / not run — {graphify_skip_msg}")
    else:
        typer.echo(
            "  graphify update .: pending / not run — graphify update . did not report completion"
        )

    if create_remote and clone_url:
        if no_git:
            typer.echo(
                f"  GitHub remote: selected {clone_url}; scaffold not pushed "
                "(--no-git); remote contents were not inspected"
            )
        elif origin_msg and commit_msg and push_msg:
            typer.echo(
                f"  GitHub remote: ran — using {clone_url}, wired origin, "
                "created the local commit, and pushed the shared history"
            )
        else:
            typer.echo(
                f"  GitHub remote: partial / pending — using {clone_url}, "
                "but local origin/commit/push did not complete"
            )
    elif remote:
        typer.echo(
            f"  GitHub remote: not run (--remote {remote} specified without --create; "
            "no GitHub API call or verification ran)"
        )
    else:
        typer.echo(
            "  GitHub remote: not selected (--create not set; no GitHub API call or "
            "verification ran)"
        )
    typer.echo(
        "  dependencies, build, and tests: not run — projboot never installs "
        "dependencies, builds code, or runs project tests"
    )

    typer.echo("First steps (user-run commands — not executed by projboot):")
    typer.echo(f"  cd {name}  [not executed]")
    if has_python:
        typer.echo(
            "  python -m venv .venv && source .venv/bin/activate && pip install -e .  "
            "[not executed]"
        )
        typer.echo("  appstarter  # or: python -m appstarter  [not executed]")
    elif has_typescript:
        typer.echo("  npm install  [not executed]")
        typer.echo("  npm run build  [not executed]")
        typer.echo("  npm start  [not executed]")
    elif has_helm:
        typer.echo(
            f"  review and customize Chart.yaml and values.yaml (placeholder image "
            f"ghcr.io/example/{name} is not a live image)  [not executed]"
        )
    elif has_rails:
        typer.echo(
            "  EXPERIMENTAL layout sketch only — missing config/boot.rb, "
            "config/environment.rb, config/routes.rb, bin/rails, Rakefile, "
            "app/views/, and db/; do not run a server expecting this layout to boot. "
            "Run `rails new` with Ruby >= 3.1 for a runnable Rails app  [not executed]"
        )
    else:
        typer.echo(
            f"  review AGENTS.md and {preset.prompts_file} to begin agent workflows "
            "(no language runtime or package manager in this scaffold)  [not executed]"
        )
    if has_graphify and not graphify_ran_msg:
        typer.echo(
            "  graphify update .  # optional: requires external graphify CLI to "
            "populate graphify-out/graph.json  [not executed]"
        )

    typer.echo("User-runnable verification checks (not executed by projboot):")
    if has_python:
        if "tests/test_appstarter.py" in files:
            typer.echo("  pip install pytest && pytest  [not executed]")
        typer.echo("  pip install build && python -m build  [not executed]")
    elif has_typescript:
        typer.echo(
            "  npm run build  # compiles src/index.ts to dist/index.js via tsc "
            "(after npm install)  [not executed]"
        )
        typer.echo(
            "  npm start  # runs node dist/index.js (no test runner or test script "
            "is configured in package.json)  [not executed]"
        )
    elif has_helm:
        typer.echo("  helm lint .  # requires helm CLI on PATH  [not executed]")
        typer.echo(
            f"  helm template {name} .  # renders manifests locally without a "
            "Kubernetes cluster  [not executed]"
        )
    elif has_rails:
        typer.echo(
            "  ruby -c config/application.rb && ruby -c "
            "app/controllers/application_controller.rb  # syntax-only check on "
            "generated files; application boot and test suite are unavailable for "
            "this experimental layout  [not executed]"
        )
    else:
        typer.echo(
            f"  no language build, lint, or test checks apply to --lang {lang} "
            "(no runtime or test runner generated)  [not executed]"
        )

    typer.echo("Unverified / pending items:")
    typer.echo(
        "  dependencies and project checks: not installed, built, or executed by projboot"
    )
    if has_rails:
        typer.echo(
            "  rails profile: experimental directory sketch only; not a bootable or "
            "verified Rails application"
        )
    if has_helm:
        typer.echo(
            "  helm deployment: local chart scaffold only; helm lint/template and "
            "Kubernetes cluster deployment were not run, and "
            f"ghcr.io/example/{name} is an unverified placeholder image"
        )
    if preset.agents:
        typer.echo(
            f"  assistant overlays ({', '.join(preset.agents)}): configuration files "
            "written; live loading in the native assistant client was not verified"
        )
    if not no_git and not git_ran_msg:
        typer.echo(
            f"  git repository: pending / not initialized "
            f"({git_skip_msg or 'git init did not complete'})"
        )
    if create_remote and clone_url and not no_git and not (
        origin_msg and commit_msg and push_msg
    ):
        typer.echo(
            "  local git remote/commit/push: pending / incomplete "
            "(origin, initial commit, or normal push did not complete)"
        )
    if has_graphify and not graphify_ran_msg:
        typer.echo(
            "  graphify knowledge graph: pending / not built (graphify-out/.gitkeep "
            "is only a placeholder until graphify update . succeeds)"
        )
    if not (create_remote and clone_url):
        typer.echo("  GitHub repository: not created or verified (--create was not run)")



def _echo_preview(
    *,
    name: str,
    lang: str,
    files: dict[str, str],
    preset: PresetConfig,
    license: str,
    remote: str | None,
    create_remote: bool,
    clone: bool,
    private: bool,
    org: str | None,
    no_git: bool,
    no_graphify: bool,
) -> None:
    """Print the composition result without writing files or running anything.

    Every line is a description of what `create` would do for these arguments:
    selected actions are marked "not executed by preview" and external
    requirements are marked "NOT CHECKED", so a selection never reads as a
    verified success.
    """
    paths = sorted(files)
    total_bytes = sum(len(content.encode()) for content in files.values())
    dirs: dict[str, None] = {}
    for rel in paths:
        for ancestor in PurePosixPath(rel).parents:
            if ancestor.as_posix() != ".":
                dirs.setdefault(ancestor.as_posix(), None)

    def integration_selected(prefix: str) -> bool:
        return any(p.startswith(prefix) for p in paths)

    typer.echo(
        f"PREVIEW `create {name}`: {len(paths)} file(s), {total_bytes} bytes "
        "composed in memory. Nothing was written; no git, Graphify, GitHub, "
        "network, or install step was run."
    )
    typer.echo("")
    typer.echo(f"Files that `create` would write to {name}/ ({len(paths)}):")
    for rel in paths:
        typer.echo(f"  {rel}")
    typer.echo(f"Directories implied by that layout ({len(dirs)}):")
    for d in dirs:
        typer.echo(f"  {d}/")
    typer.echo("Selected tools and integrations:")
    typer.echo(f"  base template (--lang): {lang}")
    typer.echo(
        f"  preset: {preset.name} (arch={preset.arch}, "
        f"outputs={preset.outputs_dir}/, scripts={preset.scripts_dir}/, "
        f"prompts={preset.prompts_file})"
    )
    typer.echo(f"  agents: {', '.join(preset.agents) if preset.agents else 'none'}")
    typer.echo(
        f"  license: {license} "
        f"({'LICENSE file selected' if 'LICENSE' in files else 'no LICENSE composed'})"
    )
    typer.echo(
        f"  graphify scaffolding (graphify-out/): "
        f"{'selected' if integration_selected('graphify-out/') else 'not selected (--no-graphify)'}"
    )
    typer.echo(
        f"  memory files (.remember/): "
        f"{'selected' if integration_selected('.remember/') else 'not selected'}"
    )
    typer.echo(
        f"  project skills (.agents/skills/): "
        f"{'selected' if integration_selected('.agents/skills/') else 'not selected'}"
    )
    typer.echo("Post-generation actions (selected by flags; preview executes none):")
    typer.echo("  write scaffold to disk: selected for `create` — not executed by preview")
    typer.echo(
        f"  git init -b main: {'selected' if not no_git else 'not selected (--no-git)'}"
        " — not executed by preview"
    )
    if not no_graphify:
        typer.echo(
            "  graphify update .: selected — not executed by preview; requirement "
            "`graphify` CLI available on PATH: NOT CHECKED by preview"
        )
    else:
        typer.echo(
            "  graphify update .: not selected (--no-graphify) — would not run on create"
        )
    if create_remote:
        visibility = "private" if private else "public"
        typer.echo(
            f"  create GitHub repository ({visibility}): selected (--create) — not "
            "executed by preview; requirement GitHub credentials + network access: "
            "NOT CHECKED by preview"
        )
        if org:
            typer.echo(f"  GitHub organization (--org): {org}")
        else:
            typer.echo(
                "  GitHub organization (--org): not specified; authenticated owner "
                "NOT CHECKED or resolved by preview"
            )
        if not no_git:
            typer.echo(
                "  connect checkout (origin + initial commit): selected — "
                "not executed by preview"
            )
        else:
            typer.echo(
                "  connect checkout: not selected (--no-git) — scaffold would not be pushed"
            )
    else:
        typer.echo(
            "  create GitHub repository: not selected (--create not set) — `create` "
            "would not touch GitHub"
        )
        if remote:
            typer.echo(
                f"  remote '{remote}' named without --create: informational only; "
                "no upload would run"
            )
    typer.echo(
        "  dependency installation: not selected — projboot never installs "
        "dependencies; not executed by preview"
    )
    typer.echo("")
    typer.echo(
        "Selected/required lines above are descriptions, not verifications: a "
        "requirement is only proven by running `create` and its checks. Re-run "
        f"these same arguments with `create {name}` to execute."
    )


@app.command()
def preview(
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
        False, "--create", help="Show whether `create` would create the remote repository"
    ),
    clone: bool = typer.Option(
        False, "--clone", help="Show whether `create` would keep a connected local checkout"
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
        False, "--no-git", help="Show `create` without `git init`"
    ),
    no_graphify: bool = typer.Option(
        False, "--no-graphify", help="Show `create` without `graphify update .`"
    ),
    force: bool = typer.Option(
        False, "--force", help="Preview a merge into a non-empty local target directory"
    ),
) -> None:
    """Show the composed project layout, selected integrations, and requested
    post-generation actions for `create` — without writing files or running anything."""
    _validate_name(name)
    _reject_contradictory_options(
        clone=clone, create_remote=create_remote, no_git=no_git
    )

    if remote is not None and remote.lower() not in ("github", "gh"):
        raise typer.BadParameter(f"Unsupported remote {remote!r}. Supported: github")

    resolved_preset, files = _resolve_options_and_compose(
        lang=lang,
        agent=agent,
        preset=preset,
        arch=arch,
        outputs_dir=outputs_dir,
        scripts_dir=scripts_dir,
        prompts_file=prompts_file,
        name=name,
        description=description,
        license=license,
        holder=holder,
        variable=variable,
        no_graphify=no_graphify,
    )

    # Fail on exactly the collisions/refusals `create` would hit, before the
    # preview claims anything. Read-only, like the rest of this command.
    _validate_write_plan(Path(name), files, force)

    _echo_preview(
        name=name,
        lang=lang,
        files=files,
        preset=resolved_preset,
        license=license,
        remote=remote,
        create_remote=create_remote,
        clone=clone,
        private=private,
        org=org,
        no_git=no_git,
        no_graphify=no_graphify,
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
        False,
        "--force",
        help="Merge into a non-empty local target or use an existing remote; pushes never rewrite remote history",
    ),
) -> None:
    """Create a project scaffold from a curated template."""
    _validate_name(name)
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
        False,
        "--force",
        help="Merge into a non-empty local target or use an existing remote; pushes never rewrite remote history",
    ),
) -> None:
    """Create a project scaffold from a dirtree layout file."""
    _validate_name(name)
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
