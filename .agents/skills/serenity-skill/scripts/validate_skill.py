#!/usr/bin/env python3
"""Lightweight Agent Skill validator for this repository."""
from __future__ import annotations

import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    end = text.find("\n---", 4)
    if end == -1:
        raise ValueError("SKILL.md frontmatter closing delimiter missing")
    front = text[4:end].strip().splitlines()
    data: dict[str, str] = {}
    for line in front:
        if not line.strip() or line.startswith(" "):
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"')
    return data


def main() -> None:
    root = (Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()).resolve()
    skill = root / "SKILL.md"
    if not skill.exists():
        raise SystemExit(f"Missing {skill}")
    data = parse_frontmatter(skill.read_text(encoding="utf-8"))
    name = data.get("name", "")
    description = data.get("description", "")
    errors = []
    if not name:
        errors.append("name is required")
    if not NAME_RE.match(name):
        errors.append("name must be lowercase letters/numbers/hyphens and cannot start/end with hyphen")
    if len(name) > 64:
        errors.append("name exceeds 64 characters")
    if root.name != name:
        errors.append(f"parent directory name '{root.name}' must match name '{name}'")
    if not description:
        errors.append("description is required")
    if len(description) > 1024:
        errors.append(f"description exceeds 1024 characters: {len(description)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print(f"OK: {name} ({len(description)} description chars)")


if __name__ == "__main__":
    main()
