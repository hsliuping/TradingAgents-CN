"""金融 schema registry。"""

from __future__ import annotations

from typing import Dict, List, Optional

from .financial_schema_models import FinancialSchemaObject, LoadedFinancialSchemaBundle


class FinancialSchemaRegistry:
    """维护已加载 bundle 的对象索引。"""

    def __init__(self):
        self._bundles: Dict[str, LoadedFinancialSchemaBundle] = {}
        self._objects_by_id: Dict[str, FinancialSchemaObject] = {}
        self._objects_by_type: Dict[str, List[FinancialSchemaObject]] = {}

    def register_bundle(self, bundle: LoadedFinancialSchemaBundle) -> None:
        self._bundles[bundle.bundle_id] = bundle
        for object_id, schema_object in bundle.objects_by_id.items():
            self._objects_by_id[object_id] = schema_object

        for object_type, objects in bundle.objects_by_type.items():
            merged = self._objects_by_type.setdefault(object_type, [])
            existing_ids = {item.id for item in merged}
            for schema_object in objects:
                if schema_object.id in existing_ids:
                    merged = [item for item in merged if item.id != schema_object.id]
                    self._objects_by_type[object_type] = merged
                    existing_ids = {item.id for item in merged}
                merged.append(schema_object)
                existing_ids.add(schema_object.id)

    def get_object(self, object_id: str) -> Optional[FinancialSchemaObject]:
        return self._objects_by_id.get(object_id)

    def has_object(self, object_id: str) -> bool:
        return object_id in self._objects_by_id

    def get_objects_by_type(self, object_type: str) -> List[FinancialSchemaObject]:
        return list(self._objects_by_type.get(object_type, []))

    def list_bundles(self) -> List[str]:
        return sorted(self._bundles.keys())

    def get_bundle_summary(self, bundle_id: str) -> Optional[dict]:
        bundle = self._bundles.get(bundle_id)
        if bundle is None:
            return None
        return {
            "bundle_id": bundle.manifest.bundle_id,
            "name": bundle.manifest.name,
            "bundle_version": bundle.manifest.bundle_version,
            "spec_version": bundle.manifest.spec_version,
            "status": bundle.manifest.status,
            "object_count": bundle.object_count,
            "object_types": {key: len(value) for key, value in bundle.objects_by_type.items()},
        }
