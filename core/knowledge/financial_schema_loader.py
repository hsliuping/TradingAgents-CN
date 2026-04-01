"""金融 schema bundle 加载器。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .financial_schema_models import (
    BundleManifest,
    FinancialSchemaObject,
    LoadedFinancialSchemaBundle,
)

logger = logging.getLogger(__name__)


class FinancialSchemaLoader:
    """从外部 schema-content 项目读取 bundle 和对象文件。"""

    def __init__(self, root_path: Optional[str | Path] = None):
        self._root_path = Path(root_path).resolve() if root_path else None

    def load_bundle(self, manifest_path: str | Path) -> LoadedFinancialSchemaBundle:
        manifest_file = Path(manifest_path).resolve()
        manifest_data = self._load_yaml_file(manifest_file)
        root_path = self._resolve_root_path(manifest_file)
        manifest = self._build_manifest(manifest_data, manifest_file)

        objects_by_id: Dict[str, FinancialSchemaObject] = {}
        objects_by_type: Dict[str, List[FinancialSchemaObject]] = {}

        for object_type, object_ids in manifest.includes.items():
            objects_by_type.setdefault(object_type, [])
            for object_id in object_ids:
                schema_object = self._load_schema_object(root_path, object_type, object_id)
                if schema_object.id in objects_by_id:
                    raise ValueError(f"Duplicate schema object id detected: {schema_object.id}")
                objects_by_id[schema_object.id] = schema_object
                objects_by_type[object_type].append(schema_object)

        logger.info(
            "[FinancialSchemaLoader] Loaded bundle %s with %s objects",
            manifest.bundle_id,
            len(objects_by_id),
        )
        return LoadedFinancialSchemaBundle(
            manifest=manifest,
            objects_by_id=objects_by_id,
            objects_by_type=objects_by_type,
        )

    def _resolve_root_path(self, manifest_file: Path) -> Path:
        if self._root_path is not None:
            return self._root_path
        try:
            return manifest_file.parents[2]
        except IndexError as exc:
            raise ValueError(f"Cannot infer schema root from manifest path: {manifest_file}") from exc

    @staticmethod
    def _load_yaml_file(file_path: Path) -> dict:
        if not file_path.exists():
            raise FileNotFoundError(f"Schema file not found: {file_path}")
        with file_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValueError(f"YAML file must contain an object: {file_path}")
        return data

    @staticmethod
    def _build_manifest(manifest_data: dict, manifest_file: Path) -> BundleManifest:
        includes = manifest_data.get("includes") or {}
        if not isinstance(includes, dict):
            raise ValueError(f"Bundle includes must be a mapping: {manifest_file}")
        normalized_includes: Dict[str, List[str]] = {}
        for object_type, object_ids in includes.items():
            if not isinstance(object_ids, list):
                raise ValueError(f"Bundle includes.{object_type} must be a list: {manifest_file}")
            normalized_includes[object_type] = [str(item) for item in object_ids]

        return BundleManifest(
            bundle_id=str(manifest_data.get("bundle_id") or ""),
            name=str(manifest_data.get("name") or ""),
            bundle_version=str(manifest_data.get("bundle_version") or ""),
            spec_version=str(manifest_data.get("spec_version") or ""),
            status=str(manifest_data.get("status") or "draft"),
            description=str(manifest_data.get("description") or ""),
            includes=normalized_includes,
            source_path=manifest_file,
        )

    def _load_schema_object(
        self,
        root_path: Path,
        object_type: str,
        object_id: str,
    ) -> FinancialSchemaObject:
        object_path = root_path / "schemas" / object_type / f"{object_id}.yaml"
        data = self._load_yaml_file(object_path)
        actual_id = str(data.get("id") or "")
        actual_type = str(data.get("object_type") or "")
        if actual_id != object_id:
            raise ValueError(f"Schema object id mismatch for {object_path}: {actual_id} != {object_id}")
        if actual_type != object_type:
            raise ValueError(
                f"Schema object type mismatch for {object_path}: {actual_type} != {object_type}"
            )
        return FinancialSchemaObject(
            id=actual_id,
            object_type=actual_type,
            name=str(data.get("name") or actual_id),
            version=str(data.get("version") or ""),
            data=data,
            source_path=object_path,
        )
