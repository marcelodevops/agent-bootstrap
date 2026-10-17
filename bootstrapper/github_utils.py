"""GitHub token handling and repo/file helpers (PyGithub)."""

from __future__ import annotations

import os

from github import Github
from github.GithubException import GithubException, UnknownObjectException
from github.Repository import Repository


def get_github() -> Github:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Environment variable GITHUB_TOKEN not set.")
    return Github(token)


def get_owner(gh: Github, org: str | None):
    return gh.get_organization(org) if org else gh.get_user()


def create_repo(owner, name: str, description: str, private: bool) -> Repository:
    try:
        return owner.get_repo(name)
    except (UnknownObjectException, ValueError):
        return owner.create_repo(name=name, description=description, private=private)


def add_file(
    repo: Repository,
    path: str,
    content: str,
    message: str = "Add file",
    branch: str | None = None,
) -> None:
    """Create a file, or overwrite it if it already exists.

    We try ``create_file`` first: it bootstraps a brand-new repo (no commits, no
    default branch yet) in one call, which ``get_contents`` cannot do. A 422
    means the path already exists, so we re-read its blob SHA and update instead.
    Intermediate directories are created implicitly from the path.
    """
    kwargs = {"branch": branch} if branch else {}
    try:
        repo.create_file(path, message, content, **kwargs)
    except GithubException as exc:
        if exc.status != 422:
            raise
        ref = branch or repo.default_branch
        existing = repo.get_contents(path, ref=ref)
        repo.update_file(path, message, content, existing.sha, **kwargs)
