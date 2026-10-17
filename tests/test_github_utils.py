from unittest.mock import MagicMock

import pytest
from github.GithubException import GithubException

from bootstrapper.github_utils import add_file, create_repo


def _unprocessible():
    return GithubException(422, {"message": "already exists"}, {})


def test_add_file_creates_on_fresh_repo():
    repo = MagicMock()
    repo.create_file.return_value = {}  # bootstraps empty repo, no error
    add_file(repo, "README.md", "hi")
    repo.create_file.assert_called_once_with("README.md", "Add file", "hi")
    repo.update_file.assert_not_called()


def test_add_file_updates_when_path_exists():
    repo = MagicMock()
    repo.create_file.side_effect = _unprocessible()
    repo.default_branch = "main"
    existing = MagicMock()
    existing.sha = "deadbeef"
    repo.get_contents.return_value = existing

    add_file(repo, "README.md", "v2", message="Update")

    repo.get_contents.assert_called_once_with("README.md", ref="main")
    repo.update_file.assert_called_once_with(
        "README.md", "Update", "v2", "deadbeef"
    )


def test_add_file_reraises_non_422():
    repo = MagicMock()
    repo.create_file.side_effect = GithubException(401, {"message": "bad"}, {})
    with pytest.raises(GithubException):
        add_file(repo, "x", "y")


def test_create_repo_returns_existing():
    owner = MagicMock()
    existing = MagicMock()
    owner.get_repo.return_value = existing
    assert create_repo(owner, "n", "d", True) is existing
    owner.create_repo.assert_not_called()


def test_create_repo_creates_when_missing():
    from github.GithubException import UnknownObjectException

    owner = MagicMock()
    owner.get_repo.side_effect = UnknownObjectException(404, {"message": "nf"}, {})
    created = MagicMock()
    owner.create_repo.return_value = created
    assert create_repo(owner, "n", "d", False) is created
    owner.create_repo.assert_called_once_with(name="n", description="d", private=False)
