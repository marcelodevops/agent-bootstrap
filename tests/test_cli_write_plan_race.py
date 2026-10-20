"""D1 correction: `create`'s non-empty refusal and write-path choice must share one preflight snapshot.

Review finding (coordination/inbox/20261020-031523-eiren-d1-review-notes.md):
`_validate_write_plan()` observed the target's non-emptiness, then `_write_local()`
re-observed it to pick merge vs staging. A target that appeared between the two
observations let `create` without `--force` enter the forced-merge path and
overwrite files. These tests simulate that race deterministically.
"""

import pytest
from typer.testing import CliRunner

import bootstrapper.cli as cli_mod
from bootstrapper.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PROJBOOT_HOME", str(tmp_path / "projboot_home"))
    monkeypatch.chdir(tmp_path)


def test_create_without_force_does_not_merge_into_target_appearing_after_preflight(
    tmp_path, monkeypatch
):
    name = "racer"
    target = tmp_path / name

    original = cli_mod._reject_resolved_collisions

    def appear_after_snapshot(planned, root):
        # Runs as the last read-only step of _validate_write_plan, i.e. strictly
        # after its non-emptiness snapshot: the target materializes mid-preflight.
        original(planned, root)
        root.mkdir(parents=True, exist_ok=True)
        (root / "README.md").write_text("PRECIOUS-USER-FILE")
        (root / "keep.txt").write_text("untouched")

    monkeypatch.setattr(cli_mod, "_reject_resolved_collisions", appear_after_snapshot)

    res = runner.invoke(
        app, ["create", name, "-l", "python", "--no-git", "--no-graphify"]
    )

    assert res.exit_code == 1, (
        "create must fail when the target appears after preflight, not merge "
        f"into it without --force:\n{res.output}"
    )
    assert (target / "README.md").read_text() == "PRECIOUS-USER-FILE"
    assert (target / "keep.txt").read_text() == "untouched"
    # No planned scaffold file may land in the target either.
    assert {p.name for p in target.iterdir()} == {"README.md", "keep.txt"}
    # And nothing else was left behind in the working directory (no staging debris).
    assert {p.name for p in tmp_path.iterdir()} == {name}


def test_create_force_still_merges_into_preexisting_nonempty_target(tmp_path):
    """Guard the other side of the review note: forced-merge behavior preserved."""
    name = "merge-target"
    target = tmp_path / name
    target.mkdir()
    (target / "keep.txt").write_text("untouched")

    res = runner.invoke(
        app, ["create", name, "-l", "python", "--no-git", "--no-graphify", "--force"]
    )

    assert res.exit_code == 0, res.output
    assert (target / "keep.txt").read_text() == "untouched"
    assert (target / "README.md").exists()
