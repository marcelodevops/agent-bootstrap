"""GitHub token handling and repo/file helpers (PyGithub)."""

from __future__ import annotations

import os

from github import Github
from github.GithubException import UnknownObjectException
from github.Repository import Repository


class RepoExistsError(RuntimeError):
    """The target repository already exists on the remote."""

    def __init__(self, full_name: str) -> None:
        super().__init__(full_name)
        self.full_name = full_name


def get_github() -> Github:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Environment variable GITHUB_TOKEN not set.")
    return Github(token)


def get_owner(gh: Github, org: str | None):
    return gh.get_organization(org) if org else gh.get_user()


def create_repo(owner, name: str, description: str, private: bool, *, force: bool = False) -> Repository:
    """Return the remote repo, creating it if missing.

    Refuses to reuse an existing repo unless ``force`` is set, so a push never
    silently overwrites an unrelated repository's files.
    """
    try:
        existing = owner.get_repo(name)
    except (UnknownObjectException, ValueError):
        return owner.create_repo(name=name, description=description, private=private)
    if not force:
        raise RepoExistsError(getattr(existing, "full_name", name))
    return existing
