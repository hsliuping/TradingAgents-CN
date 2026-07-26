"""Create-only MongoDB index initialization for AlphaGuard PR-003/PR-004."""

from __future__ import annotations

from typing import Any

from tradingagents.alphaguard.mongo_indexes import ALPHAGUARD_INDEX_SPECS


def _normalized_keys(value: Any) -> list[tuple[str, int]]:
    if hasattr(value, "items"):
        return [(str(key), int(direction)) for key, direction in value.items()]
    return [(str(key), int(direction)) for key, direction in value]


async def ensure_alphaguard_indexes(db) -> list[str]:
    """Create only missing indexes; fail on any name/options conflict."""

    actions: list[str] = []
    for collection_name, specs in ALPHAGUARD_INDEX_SPECS.items():
        collection = db[collection_name]
        existing = {
            index["name"]: index
            for index in await collection.list_indexes().to_list(length=None)
        }
        for spec in specs:
            current = existing.get(spec["name"])
            if current is not None:
                expected_keys = _normalized_keys(spec["keys"])
                current_keys = _normalized_keys(current["key"])
                expected_unique = bool(spec.get("unique", False))
                current_unique = bool(current.get("unique", False))
                if (
                    current_keys != expected_keys
                    or current_unique != expected_unique
                ):
                    raise RuntimeError(
                        f"AlphaGuard index conflict: {collection_name}."
                        f"{spec['name']} existing={current_keys}/{current_unique} "
                        f"expected={expected_keys}/{expected_unique}"
                    )
                actions.append(f"unchanged {collection_name}.{spec['name']}")
                continue
            await collection.create_index(
                spec["keys"],
                name=spec["name"],
                unique=bool(spec.get("unique", False)),
            )
            actions.append(f"created {collection_name}.{spec['name']}")
    return actions
