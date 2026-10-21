"""A3 contract: validate a project before touching the filesystem, and publish a
new project atomically.

Reproduced product gaps this closes:

* A project ``name`` doubles as the local directory, so a path/absolute/traversal
  name (``../evil``, ``/etc/passwd``, ``sub/out``) escapes the intended output, and a
  control-character name (``foo\\nbar``) is an unusable package/repository identity
  and a metadata-injection vector. Nothing rejected these before A3.
* Contradictory options were half-ignored instead of rejected: ``--clone --no-git``
  printed a note and "succeeded" while producing no connected repo, and ``--clone``
  without ``--create`` had no remote to connect to.
* A brand-new project was written file-by-file straight into the final target, so a
  mid-write failure (disk full, permission) left a *partial* project and staging
  never existed to be cleaned. A3 writes the whole scaffold in a temporary sibling
  and renames it into place only after every file succeeds; on failure it removes
  only its own staging and leaves the requested target absent.
* Overwriting an existing directory with ``--force`` could crash partway when a
  planned file collided with an existing directory of the same name
  (``IsADirectoryError``/``FileExistsError``), after earlier files were already
  written into the real target. A3 preflights that filesystem type conflict first.

The accepted A1 resolved-alias and symlink-containment safeguards live in
tests/test_output_path_contract.py and are re-checked here only at the write
boundary; nothing in this file replaces them.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from bootstrapper.cli import _write_local, app

runner = CliRunner()


def _run(args):
    return runner.invoke(app, args)


def _local_create_env(tmp_path, monkeypatch) -> Path:
    """Run the CLI from an isolated working dir so writes and presets stay local.

    Returns the working directory; PROJBOOT_HOME is kept OUTSIDE it so a
    scaffold run only ever adds the project directory under the returned path.
    """
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "cfg"))
    return work


# --- identity: a usable package/repository name, validated before any write ---

VALID_NAMES = [
    "demo",
    "svc",
    "proj",
    "new-project",  # hyphen (npm / GitHub)
    "my_app",  # underscore
    "core.v2",  # dotted (module-ish)
    "app1",  # digit-led
    "café",  # unicode letter, no separator / control char
    "x",  # shortest usable identity
]


@pytest.mark.parametrize("name", VALID_NAMES)
def test_valid_names_are_accepted(name, tmp_path, monkeypatch):
    work = _local_create_env(tmp_path, monkeypatch)
    res = _run(["create", name, "-l", "none", "--no-git", "--no-graphify"])
    assert res.exit_code == 0, res.output
    assert (work / name).is_dir()


@pytest.mark.parametrize(
    "name",
    [
        "",  # empty: not an identity
        ".",  # current dir
        "..",  # parent dir
        "/etc/passwd",  # absolute path
        "../evil",  # parent traversal
        "sub/out",  # nested path, not a single name
        "foo bar",  # internal space
        "café/qux",  # unicode is fine, the separator is not
        "foo\nbar",  # control char: metadata / terminal injection
        "-lead",  # option-like, cannot be a package identity
        "demo\n",  # trailing newline: terminal injection, and '$' almost let it pass
        "demo\r\n",  # CRLF-terminated identity
        "demo\r",  # bare trailing carriage return
    ],
)
def test_invalid_names_are_rejected_without_writing(name, tmp_path, monkeypatch):
    work = _local_create_env(tmp_path, monkeypatch)
    before = set(work.iterdir())
    res = _run(["create", name, "-l", "none", "--no-git", "--no-graphify"])
    assert res.exit_code != 0
    # Rejected before compose/write: nothing new is added under the working dir
    # and no directory named after the requested identity is created. This uses
    # a set comparison instead of `work / name` because an absolute or "." name
    # collapses onto pre-existing paths and would make that check trivially true.
    assert set(work.iterdir()) == before
    if name and not name.startswith(("/", ".")):
        assert not (work / name).exists()


def test_invalid_name_reports_the_identity_contract(tmp_path, monkeypatch):
    _local_create_env(tmp_path, monkeypatch)
    res = _run(["create", "../evil", "-l", "none", "--no-git", "--no-graphify"])
    assert res.exit_code != 0
    assert "name" in res.output.lower()


@pytest.mark.parametrize("name", ["demo\n", "demo\r\n", "demo\r"])
def test_trailing_line_ending_name_writes_nothing_anywhere(
    name, tmp_path, monkeypatch, hook_guard
):
    # Blocking A3 review finding: a regex ending in `$` also matches a position
    # before a terminal newline, so "demo\n" sailed through _validate_name and the
    # scaffold was written to a newline-named directory. Identity validation must
    # be a complete-string check. The remote layer is monkeypatched to fail loudly
    # so this also proves --create never reaches a remote write.
    import bootstrapper.github_utils as gu

    work = _local_create_env(tmp_path, monkeypatch)
    before = set(work.iterdir())
    remote_calls: list[str] = []

    def _remote_spy(*args, **kwargs):
        remote_calls.append("called")
        raise AssertionError("a rejected identity must never touch the remote layer")

    monkeypatch.setattr(gu, "get_github", _remote_spy)
    monkeypatch.setattr(gu, "get_owner", _remote_spy)
    monkeypatch.setattr(gu, "create_repo", _remote_spy)

    res = _run(
        ["create", name, "-l", "none", "--no-git", "--no-graphify",
         "-r", "github", "--create"]
    )
    assert res.exit_code != 0
    assert set(work.iterdir()) == before  # no destination directory anywhere
    assert hook_guard == []  # no post-scaffold hooks
    assert remote_calls == []  # no remote write attempted


# --- option combinations: reject plainly contradictory ones before writes ------


@pytest.fixture
def hook_guard(monkeypatch):
    """Fail loudly if any post-scaffold hook runs; also blocks git/graphify."""
    calls: list[str] = []

    def _boom(*args, **kwargs):
        calls.append("called")
        raise AssertionError("run_post_hooks must not run for a rejected invocation")

    monkeypatch.setattr("bootstrapper.cli.run_post_hooks", _boom)
    return calls


@pytest.mark.parametrize(
    "extra",
    [
        ["--clone"],  # clone with no remote creation to connect to
        ["--clone", "--no-git"],  # clone needs git; --no-git contradicts it
    ],
)
def test_contradictory_clone_options_rejected_before_hooks(
    extra, tmp_path, monkeypatch, hook_guard
):
    work = _local_create_env(tmp_path, monkeypatch)
    res = _run(["create", "proj", "-l", "none", "--no-graphify", *extra])
    assert res.exit_code != 0
    assert "clone" in res.output.lower()
    assert hook_guard == []  # no post hooks ran
    assert not (work / "proj").exists()  # and nothing was written


def test_remote_without_create_is_informational_not_rejected(tmp_path, monkeypatch):
    # --remote without --create keeps the existing documented "not uploading" note;
    # it is not a contradiction and must still succeed for a local scaffold.
    work = _local_create_env(tmp_path, monkeypatch)
    res = _run(
        ["create", "proj", "-l", "none", "--no-git", "--no-graphify", "-r", "github"]
    )
    assert res.exit_code == 0, res.output
    assert (work / "proj").is_dir()  # no network, no remote, just a local project


# --- staging: a new project publishes atomically ------------------------------


def test_successful_new_creation_publishes_all_files_and_no_staging_leaks(
    tmp_path, monkeypatch
):
    work = _local_create_env(tmp_path, monkeypatch)
    before = set(work.iterdir())
    res = _run(["create", "demo", "-l", "python", "--no-git", "--no-graphify"])
    assert res.exit_code == 0, res.output
    proj = work / "demo"
    assert proj.is_dir() and any(proj.iterdir())
    assert (proj / "pyproject.toml").exists()
    # Only the target was added under work: the temporary sibling is gone.
    assert set(work.iterdir()) - before == {proj}


def test_injected_write_failure_leaves_no_partial_target_or_staging(
    tmp_path, monkeypatch
):
    # Simulate a mid-write disk failure while scaffolding a brand-new target.
    target = tmp_path / "demo"
    before = set(tmp_path.iterdir())
    original = Path.write_text

    def flaky(self, data, *args, **kwargs):
        if self.name == "BIG.txt":
            raise OSError(28, "No space left on device")
        return original(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky)
    files = {"a.txt": "ok", "BIG.txt": "boom", "c.txt": "ok"}
    with pytest.raises(typer.Exit):
        _write_local(target, files, force=False)

    # The requested target was never created...
    assert not target.exists()
    # ...and nothing of ours is left behind (staging removed, no partial files).
    assert set(tmp_path.iterdir()) == before


def test_staging_rejects_a_write_that_would_escape_the_target(tmp_path):
    # A plan that resolves outside the target aborts before staging is created,
    # so no temporary sibling is orphaned either.
    target = tmp_path / "out"
    with pytest.raises(typer.Exit):
        _write_local(target, {"sub/../../escape.txt": "bad"}, force=False)
    assert not (tmp_path / "escape.txt").exists()
    assert not target.exists()
    assert set(tmp_path.iterdir()) == set()


# --- existing targets: preflight filesystem type conflicts before any write ----


def test_existing_file_named_like_planned_dir_aborts_with_no_writes(tmp_path):
    # The target exists but a planned directory's name is occupied by a file.
    # Writing straight in would crash half-way after creating a sibling file.
    target = tmp_path / "demo"
    target.mkdir()
    (target / "src").write_text("I am a file, not the directory the plan needs")
    files = {"README.md": "readme", "src/main.py": "entry"}

    with pytest.raises(typer.Exit):
        _write_local(target, files, force=True)

    # No partial writes into the real target.
    assert not (target / "README.md").exists()
    assert not (target / "src" / "main.py").exists()
    # The pre-existing file is untouched.
    assert (target / "src").read_text().startswith("I am a file")


def test_force_preserves_unrelated_existing_files(tmp_path, monkeypatch):
    work = _local_create_env(tmp_path, monkeypatch)
    (work / "demo").mkdir()
    (work / "demo" / "keep.txt").write_text("precious")
    res = _run(
        ["create", "demo", "-l", "python", "--no-git", "--no-graphify", "--force"]
    )
    assert res.exit_code == 0, res.output
    assert (work / "demo" / "keep.txt").read_text() == "precious"  # unrelated kept
    assert (work / "demo" / "pyproject.toml").exists()  # scaffold merged in


def test_nonempty_target_without_force_is_refused(tmp_path):
    target = tmp_path / "demo"
    target.mkdir()
    (target / "keep.txt").write_text("precious")
    with pytest.raises(typer.Exit):
        _write_local(target, {"README.md": "readme"}, force=False)
    assert (target / "keep.txt").read_text() == "precious"
    assert not (target / "README.md").exists()
