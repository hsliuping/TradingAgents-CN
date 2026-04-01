"""金融 schema bundle 服务骨架。"""

from __future__ import annotations

import logging
import os
from typing import Iterable, List, Optional

from core.knowledge.financial_schema_loader import FinancialSchemaLoader
from core.knowledge.financial_schema_models import FinancialSchemaObject, LoadedFinancialSchemaBundle
from core.knowledge.financial_schema_registry import FinancialSchemaRegistry

logger = logging.getLogger(__name__)

_DEFAULT_SCHEMA_BUNDLE_SERVICE: Optional["SchemaBundleService"] = None


class SchemaBundleService:
    """统一的 bundle 加载与查询入口。"""

    def __init__(self, root_path: Optional[str] = None):
        self._root_path = root_path or os.environ.get("FINANCIAL_SCHEMA_BUNDLE_ROOT")
        self._loader = FinancialSchemaLoader(self._root_path)
        self._registry = FinancialSchemaRegistry()

    def autoload_from_env(self) -> List[LoadedFinancialSchemaBundle]:
        manifests_value = os.environ.get("FINANCIAL_SCHEMA_BUNDLE_MANIFESTS", "")
        manifest_paths = [item.strip() for item in manifests_value.split(os.pathsep) if item.strip()]
        if not manifest_paths:
            return []
        return self.load_bundles(manifest_paths)

    def load_bundle(self, manifest_path: str) -> LoadedFinancialSchemaBundle:
        bundle = self._loader.load_bundle(manifest_path)
        self._registry.register_bundle(bundle)
        logger.info(
            "[SchemaBundleService] Registered bundle %s (%s objects)",
            bundle.bundle_id,
            bundle.object_count,
        )
        return bundle

    def load_bundles(self, manifest_paths: Iterable[str]) -> List[LoadedFinancialSchemaBundle]:
        return [self.load_bundle(path) for path in manifest_paths]

    def get_schema_object(self, object_id: str) -> Optional[FinancialSchemaObject]:
        return self._registry.get_object(object_id)

    def has_schema_object(self, object_id: str) -> bool:
        return self._registry.has_object(object_id)

    def get_schema_objects_by_type(self, object_type: str) -> List[FinancialSchemaObject]:
        return self._registry.get_objects_by_type(object_type)

    def list_loaded_bundles(self) -> List[str]:
        return self._registry.list_bundles()

    def get_bundle_summary(self, bundle_id: str) -> Optional[dict]:
        return self._registry.get_bundle_summary(bundle_id)


def get_default_schema_bundle_service() -> SchemaBundleService:
    global _DEFAULT_SCHEMA_BUNDLE_SERVICE
    if _DEFAULT_SCHEMA_BUNDLE_SERVICE is None:
        service = SchemaBundleService()
        try:
            loaded = service.autoload_from_env()
            if loaded:
                logger.info(
                    "[SchemaBundleService] Auto-loaded %s bundle(s) from env",
                    len(loaded),
                )
        except Exception as exc:
            logger.warning("[SchemaBundleService] Failed to autoload bundle manifests: %s", exc)
        _DEFAULT_SCHEMA_BUNDLE_SERVICE = service
    return _DEFAULT_SCHEMA_BUNDLE_SERVICE
