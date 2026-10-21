from unittest.mock import MagicMock

import pytest

from bootstrapper.github_utils import RepoExistsError, create_repo


def test_create_repo_refuses_existing_without_force():
    owner = MagicMock()
    existing = MagicMock()
    existing.full_name = "acme/n"
    owner.get_repo.return_value = existing
    with pytest.raises(RepoExistsError):
        create_repo(owner, "n", "d", True)
    owner.create_repo.assert_not_called()


def test_create_repo_returns_existing_with_force():
    owner = MagicMock()
    existing = MagicMock()
    owner.get_repo.return_value = existing
    assert create_repo(owner, "n", "d", True, force=True) is existing
    owner.create_repo.assert_not_called()


def test_create_repo_creates_when_missing():
    from github.GithubException import UnknownObjectException

    owner = MagicMock()
    owner.get_repo.side_effect = UnknownObjectException(404, {"message": "nf"}, {})
    created = MagicMock()
    owner.create_repo.return_value = created
    assert create_repo(owner, "n", "d", False) is created
    owner.create_repo.assert_called_once_with(name="n", description="d", private=False)
