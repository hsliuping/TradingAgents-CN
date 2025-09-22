"""Util functions which are explicitly not part of the public API."""

from pathlib import Path


def is_path_inside(child_path: Path, parent_path: Path) -> bool:
    """Check if the child path is inside the parent path."""
    return parent_path.resolve() in child_path.resolve().parents
