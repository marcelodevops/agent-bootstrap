"""A1 contract: reject output-destination collisions before anything is written.

Covers the two reproduced product failures and the general path contract:

* ``--prompts-file ./README.md`` must not silently overwrite the template
  ``README.md`` (two aliases of the same destination).
* ``--prompts-file src`` must not leave a half-written project when a rendered
  file collides with a directory ancestor produced by another layer.

The guard must run *before* the first ``write_text``/``mkdir`` so an invalid
combination never creates any target file, while the existing containment and
symlink protections stay intact.
"""

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from bootstrapper.cli import _write_local, app
from bootstrapper.composer import (
    PathCollisionError,
    compose_project_files,
    find_output_conflicts,
)
from bootstrapper.presets import resolve_preset

runner = CliRunner()


def _run(args):
    return runner.invoke(app, args)


# --- find_output_conflicts: the pure, reusable contract ---------------------


def test_find_output_conflicts_allows_disjoint_paths():
    # Shared ancestors (.github) that are never themselves a file must not trip.
    find_output_conflicts(
        {
            ".github/workflows/ci.yml": "ci",
            ".github/copilot-instructions.md": "copilot",
            "src/main.py": "entry",
            "README.md": "readme",
        }
    )


def test_find_output_conflicts_rejects_same_destination_alias():
    with pytest.raises(PathCollisionError, match="same output"):
        find_output_conflicts({"README.md": "readme", "./README.md": "prompts"})


def test_find_output_conflicts_allows_identical_alias():
    # Same destination + same content is harmless: nothing is silently lost.
    find_output_conflicts({"README.md": "x", "./README.md": "x"})


def test_find_output_conflicts_rejects_file_over_directory():
    with pytest.raises(PathCollisionError, match="directory"):
        find_output_conflicts({"src": "prompts", "src/main.py": "entry"})


# --- compose_project_files surfaces the contract early ----------------------


def test_compose_rejects_alias_of_readme(tmp_path):
    preset = resolve_preset("default", prompts_file="./README.md", agents=[])
    with pytest.raises(PathCollisionError):
        compose_project_files(
            name="p", description="d", lang="python", preset=preset,
            config_dir=tmp_path,
        )


def test_compose_rejects_file_colliding_with_src_dir(tmp_path):
    preset = resolve_preset("default", prompts_file="src", agents=[])
    with pytest.raises(PathCollisionError):
        compose_project_files(
            name="p", description="d", lang="python", preset=preset,
            config_dir=tmp_path,
        )


# --- CLI: clear validation error and no target files ------------------------


def test_cli_rejects_prompts_file_alias_overwriting_readme(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "home"))
    res = _run(
        ["create", "proj", "-l", "python", "--prompts-file", "./README.md",
         "--no-git", "--no-graphify"]
    )
    assert res.exit_code != 0
    assert "same output" in res.output
    # Nothing was scaffolded: the destination dir is never created.
    assert not (tmp_path / "proj").exists()


def test_cli_rejects_prompts_file_colliding_with_src_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "home"))
    res = _run(
        ["create", "proj", "-l", "python", "--prompts-file", "src",
         "--no-git", "--no-graphify"]
    )
    assert res.exit_code != 0
    assert "directory" in res.output
    # A detectable conflict must not leave a partially written project behind.
    assert not (tmp_path / "proj" / "src").exists()


# --- _write_local: the universal write-boundary gate ------------------------


def test_write_local_rejects_alias_no_partial(tmp_path):
    files = {"keep.txt": "data", "./keep.txt": "different"}
    with pytest.raises(typer.Exit):
        _write_local(tmp_path / "out", files, force=False)
    # Neither alias may be written because validation precedes every write.
    assert not (tmp_path / "out").exists()


def test_write_local_rejects_file_dir_ancestor_no_partial(tmp_path):
    files = {"src": "prompts", "src/main.py": "entry", "a.txt": "data"}
    with pytest.raises(typer.Exit):
        _write_local(tmp_path / "out", files, force=False)
    assert not (tmp_path / "out").exists()


def test_write_local_preserves_symlink_containment(tmp_path):
    # A symlinked ancestor must not let a write escape the target dir.
    out = tmp_path / "out"
    out.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (out / "escape_link").symlink_to(outside)
    with pytest.raises(typer.Exit):
        _write_local(out, {"escape_link/leak.txt": "secret"}, force=True)
    assert not (outside / "leak.txt").exists()


def test_write_local_allows_identical_alias_writes_once(tmp_path):
    files = {"README.md": "same", "./README.md": "same"}
    _write_local(tmp_path / "out", files, force=False)
    assert (tmp_path / "out" / "README.md").read_text() == "same"


# --- correction round: resolved-destination aliases lexical checks miss ------


def test_write_local_rejects_parent_traversal_alias(tmp_path):
    # 'dir/../README.md' and 'README.md' unify only after resolve() collapses
    # '..', so the earlier lexical normalization let the last write win.
    files = {"README.md": "first", "dir/../README.md": "second"}
    with pytest.raises(typer.Exit):
        _write_local(tmp_path / "out", files, force=False)
    assert not (tmp_path / "out").exists()


def test_write_local_rejects_in_root_symlink_alias(tmp_path):
    # 'alias' -> 'real' symlink: both rels resolve to real/file.txt with
    # different content; must abort before the second write overwrites the first.
    out = tmp_path / "out"
    (out / "real").mkdir(parents=True)
    (out / "alias").symlink_to(out / "real")
    files = {"real/file.txt": "first", "alias/file.txt": "second"}
    with pytest.raises(typer.Exit):
        _write_local(out, files, force=True)
    # Caught pre-write, so the collision never materialized.
    assert not (out / "real" / "file.txt").exists()


def test_write_local_rejects_resolved_file_over_directory(tmp_path):
    # The file/dir conflict only appears after resolve() collapses 'dir/..',
    # which the lexical PurePosixPath pass cannot see.
    files = {"src": "prompts", "dir/../src/main.py": "entry"}
    with pytest.raises(typer.Exit):
        _write_local(tmp_path / "out", files, force=False)
    assert not (tmp_path / "out").exists()
