"""Parser for classic `tree`-style directory listings.

Handles both Unicode (``├── └── │``) and ASCII (``|-- `-- |``) glyphs,
plus plain indentation-only layouts.
"""

from __future__ import annotations

from pathlib import Path

# Each prefix element is the 4-char column block preceding a depth level.
_UNICODE_PREFIXES = ("    ", "│   ")
_ASCII_PREFIXES = ("    ", "|   ")


def _strip_connector(stripped: str) -> tuple[str, bool]:
    """Return (name, is_dir) after removing a tree connector, if present."""
    for c in ("├── ", "└── ", "|-- ", "`-- "):
        if stripped.startswith(c):
            body = stripped[len(c) :]
            return body.rstrip(), body.endswith("/")
    return stripped.rstrip(), stripped.endswith("/")


def parse_dirtree(text: str) -> dict:
    """Parse a dirtree listing into a nested ``{name: children}`` dict.

    A directory's children live under its key; files map to ``None``.
    The root entry (first non-blank line) becomes the outermost dict key.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return {}

    root_raw, root_is_dir = _strip_connector(lines[0].strip())
    root_name = root_raw.rstrip("/")
    if not root_is_dir and "." in root_name:
        # Single-file "tree" output: root itself is a file.
        return {root_name: None}

    root_children: dict = {}
    root: dict = {root_name: root_children}
    # stack[k] is the children dict for entries at depth k; stack[0] = root's.
    stack: list[dict] = [root_children]

    for line in lines[1:]:
        prefixes, name_part = _split_prefix(line)
        level = len(prefixes)
        name, is_dir = _strip_connector(name_part.strip())
        name = name.rstrip("/")

        # Clamp to the deepest known frame, then drop deeper frames so the
        # parent is the dict at this line's level.
        level = min(level, len(stack) - 1)
        del stack[level + 1 :]
        parent = stack[level]

        if is_dir:
            child: dict = {}
            parent[name] = child
            stack.append(child)
        else:
            parent[name] = None

    return root


def _split_prefix(line: str) -> tuple[list[str], str]:
    """Split a body line into fixed-width prefix columns and the remainder."""
    prefixes: list[str] = []
    rest = line
    candidates = _UNICODE_PREFIXES + _ASCII_PREFIXES
    while len(rest) >= 4 and rest[:4] in candidates:
        prefixes.append(rest[:4])
        rest = rest[4:]
    return prefixes, rest


def flatten(tree: dict, prefix: str = "") -> list[str]:
    """Yield newline-free paths for every file and directory in a parsed tree.

    Directories are suffixed with ``/``; files are not.
    """
    out: list[str] = []
    for name, children in tree.items():
        path = f"{prefix}{name}"
        if children is None:
            out.append(path)
        else:
            out.append(f"{path}/")
            out.extend(flatten(children, f"{path}/"))
    return out


def empty_dirs(entries: list[str]) -> list[str]:
    """Directories (explicit or implied) that contain no files."""
    dirs: set[str] = set()
    files: set[str] = set()
    for e in entries:
        if e.endswith("/"):
            dirs.add(e.rstrip("/"))
        else:
            files.add(e)
            parts = e.split("/")
            for i in range(1, len(parts)):  # all ancestors are dirs
                dirs.add("/".join(parts[:i]))
    return sorted(
        d
        for d in dirs
        if not any(f == d or f.startswith(d + "/") for f in files)
    )


def read_tree_file(path: Path) -> dict:
    return parse_dirtree(path.read_text())
