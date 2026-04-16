import argparse
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from pymongo import MongoClient

from app.core.config import settings
from tradingagents.llm_clients.provider_keys import canonical_aliases, normalize_provider_key


def _now() -> str:
    return datetime.utcnow().isoformat()


def _merge_aliases(*values: Iterable[str]) -> List[str]:
    merged: List[str] = []
    seen = set()
    for value in values:
        for item in value or []:
            item_str = str(item).strip()
            if not item_str:
                continue
            lowered = item_str.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            merged.append(item_str)
    return merged


def _pick_value(primary: Dict[str, Any], secondary: Dict[str, Any], key: str):
    primary_value = primary.get(key)
    if primary_value not in (None, "", [], {}):
        return primary_value
    return secondary.get(key)


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _should_run(section: str, include: Optional[Sequence[str]], exclude: Sequence[str]) -> bool:
    if include and section not in include:
        return False
    if section in exclude:
        return False
    return True


def normalize_llm_providers(db, dry_run: bool = False, fix_indexes: bool = False) -> Dict[str, Any]:
    coll = db.llm_providers
    docs = list(coll.find())
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for doc in docs:
        canonical = normalize_provider_key(doc.get("name"))
        grouped.setdefault(canonical, []).append(doc)

    renamed = 0
    merged = 0
    for canonical, items in grouped.items():
        preferred = next((doc for doc in items if doc.get("name") == canonical), items[0])
        aliases = canonical_aliases(canonical)
        for doc in items:
            if doc is preferred:
                continue
            aliases.append(doc.get("name", ""))
            aliases.extend(doc.get("aliases", []))
            merged += 1

        update_doc = {
            "name": canonical,
            "display_name": _pick_value(preferred, {}, "display_name"),
            "description": _pick_value(preferred, {}, "description"),
            "website": _pick_value(preferred, {}, "website"),
            "api_doc_url": _pick_value(preferred, {}, "api_doc_url"),
            "logo_url": _pick_value(preferred, {}, "logo_url"),
            "is_active": preferred.get("is_active", True),
            "supported_features": preferred.get("supported_features", []),
            "default_base_url": _pick_value(preferred, {}, "default_base_url"),
            "api_key": _pick_value(preferred, {}, "api_key"),
            "api_secret": _pick_value(preferred, {}, "api_secret"),
            "aliases": [a for a in _merge_aliases(aliases, preferred.get("aliases", [])) if normalize_provider_key(a) != canonical],
            "extra_config": preferred.get("extra_config", {}),
            "is_aggregator": preferred.get("is_aggregator", False),
            "aggregator_type": preferred.get("aggregator_type"),
            "model_name_format": preferred.get("model_name_format"),
            "created_at": preferred.get("created_at"),
            "updated_at": _now(),
        }

        if preferred.get("name") != canonical:
            renamed += 1

        if not dry_run:
            coll.replace_one({"_id": preferred["_id"]}, {**preferred, **update_doc})
            duplicate_ids = [doc["_id"] for doc in items if doc["_id"] != preferred["_id"]]
            if duplicate_ids:
                coll.delete_many({"_id": {"$in": duplicate_ids}})

    if not dry_run and fix_indexes:
        try:
            coll.create_index("name", unique=True, name="uniq_provider_name")
        except Exception:
            pass

    return {"providers_total": len(docs), "providers_renamed": renamed, "providers_merged": merged}


def normalize_system_configs(db, dry_run: bool = False) -> Dict[str, Any]:
    coll = db.system_configs
    docs = list(coll.find())
    changed_docs = 0
    changed_entries = 0

    for doc in docs:
        llm_configs = doc.get("llm_configs", [])
        changed = False
        for item in llm_configs:
            original = item.get("provider")
            normalized = normalize_provider_key(original)
            if original and normalized != original:
                item["provider"] = normalized
                changed = True
                changed_entries += 1

        if changed:
            changed_docs += 1
            if not dry_run:
                coll.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"llm_configs": llm_configs, "updated_at": _now()}},
                )

    return {"system_configs_changed": changed_docs, "llm_config_entries_changed": changed_entries}


def normalize_model_catalog(db, dry_run: bool = False, fix_indexes: bool = False) -> Dict[str, Any]:
    coll = db.model_catalog
    docs = list(coll.find())
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for doc in docs:
        canonical = normalize_provider_key(doc.get("provider"))
        grouped.setdefault(canonical, []).append(doc)

    merged_catalogs = 0
    for canonical, items in grouped.items():
        preferred = next((doc for doc in items if doc.get("provider") == canonical), items[0])
        models_by_name: Dict[str, Dict[str, Any]] = {}
        for doc in items:
            for model in doc.get("models", []):
                model_name = model.get("name")
                if model_name and model_name not in models_by_name:
                    models_by_name[model_name] = model

        updated = {
            **preferred,
            "provider": canonical,
            "models": list(models_by_name.values()),
            "updated_at": _now(),
        }

        if not dry_run:
            coll.replace_one({"_id": preferred["_id"]}, updated)
            duplicate_ids = [doc["_id"] for doc in items if doc["_id"] != preferred["_id"]]
            if duplicate_ids:
                coll.delete_many({"_id": {"$in": duplicate_ids}})

        merged_catalogs += max(0, len(items) - 1)

    if not dry_run and fix_indexes:
        try:
            coll.create_index("provider", unique=True, name="uniq_model_catalog_provider")
        except Exception:
            pass

    return {"model_catalog_groups": len(grouped), "model_catalog_merged": merged_catalogs}


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="normalize_provider_keys")
    parser.add_argument("--mongo-uri", default=settings.MONGO_URI)
    parser.add_argument("--database", default=settings.MONGO_DB)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--include", default="", help="Comma-separated sections: providers,system_configs,model_catalog")
    parser.add_argument("--exclude", default="", help="Comma-separated sections to skip")
    parser.add_argument("--fix-indexes", action="store_true", help="Recreate unique indexes for normalized keys")
    args = parser.parse_args(list(argv) if argv is not None else None)

    include = _split_csv(args.include) or None
    exclude = _split_csv(args.exclude)

    client = MongoClient(args.mongo_uri)
    try:
        db = client[args.database]
        summary: Dict[str, Any] = {
            "database": args.database,
            "dry_run": args.dry_run,
            "include": include or ["providers", "system_configs", "model_catalog"],
            "exclude": exclude,
            "fix_indexes": args.fix_indexes,
        }
        if _should_run("providers", include, exclude):
            summary.update(normalize_llm_providers(db, dry_run=args.dry_run, fix_indexes=args.fix_indexes))
        if _should_run("system_configs", include, exclude):
            summary.update(normalize_system_configs(db, dry_run=args.dry_run))
        if _should_run("model_catalog", include, exclude):
            summary.update(normalize_model_catalog(db, dry_run=args.dry_run, fix_indexes=args.fix_indexes))
        print(summary)
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
