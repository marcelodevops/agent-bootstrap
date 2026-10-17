import textwrap

from bootstrapper.dirtree import empty_dirs, flatten, parse_dirtree
from bootstrapper.templates import get_template, render

TREE = textwrap.dedent(
    """\
    myproject/
    ├── charts/
    │   └── api/
    │       ├── Chart.yaml
    │       └── values.yaml
    ├── src/
    │   ├── index.ts
    │   └── lib/
    │       └── util.ts
    ├── docs/
    └── README.md
    """
)


def test_parse_root_and_files():
    tree = parse_dirtree(TREE)
    paths = set(flatten(tree))
    assert "myproject/" in paths
    assert "myproject/charts/api/Chart.yaml" in paths
    assert "myproject/src/lib/util.ts" in paths
    assert "myproject/README.md" in paths


def test_explicit_empty_dir_detected():
    # Regression: `docs/` (explicit trailing slash, no children) must be listed.
    entries = flatten(parse_dirtree(TREE))
    assert "myproject/docs/" in entries
    assert "myproject/docs" in empty_dirs(entries)


def test_empty_dirs_excludes_dirs_with_files():
    entries = flatten(parse_dirtree(TREE))
    empties = empty_dirs(entries)
    assert "myproject/charts" not in empties  # has api/ under it
    assert "myproject/src" not in empties


def test_ascii_tree_variant():
    ascii_tree = textwrap.dedent(
        """\
        app/
        |-- src/
        |   `-- main.py
        `-- README.md
        """
    )
    paths = set(flatten(parse_dirtree(ascii_tree)))
    assert "app/src/main.py" in paths
    assert "app/README.md" in paths


def test_helm_go_template_passthrough():
    body = get_template("helm-chart")["files"]["templates/deployment.yaml"]
    out = render(body, name="demo", description="d", year="2026", holder="acme")
    assert "{{ .Values.replicaCount }}" in out
    assert '{{- include "demo.labels" . | nindent 4 }}' in out
    assert "name: demo" in out


def test_github_actions_dollar_brace_passthrough():
    body = "${{ secrets.GITHUB_TOKEN }} and ${{ matrix.os }}"
    assert render(body, name="demo") == body


def test_safe_join_rejects_escape_and_empty():
    import pytest

    from bootstrapper.cli import _safe_join
    from pathlib import Path

    with pytest.raises(ValueError):
        _safe_join(Path("out"), "../evil")
    with pytest.raises(ValueError):
        _safe_join(Path("out"), "")


def test_root_entry_not_treated_as_file():
    # Regression: the root dir line must not become an empty-named file.
    from bootstrapper.cli import init_from_tree  # noqa: F401  (import smoke)

    tree = parse_dirtree(TREE)
    entries = flatten(tree)
    root_prefix = "myproject/"
    rel = [e[len(root_prefix) :] for e in entries if e.startswith(root_prefix)]
    file_rels = [r for r in rel if r and not r.endswith("/")]
    assert "" not in file_rels
    assert "README.md" in file_rels
