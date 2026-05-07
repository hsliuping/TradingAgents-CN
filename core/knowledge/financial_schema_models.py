"""结构化金融 schema 对象模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class FinancialSchemaObject:
    """单个金融 schema 对象。"""

    id: str
    object_type: str
    name: str
    version: str
    data: Dict[str, Any]
    source_path: Path

    @property
    def summary(self) -> str:
        return str(self.data.get("summary") or "")

    @property
    def status(self) -> str:
        return str(self.data.get("status") or "draft")


@dataclass(frozen=True)
class BundleManifest:
    """bundle 描述文件。"""

    bundle_id: str
    name: str
    bundle_version: str
    spec_version: str
    status: str
    description: str
    includes: Dict[str, List[str]] = field(default_factory=dict)
    source_path: Optional[Path] = None


@dataclass(frozen=True)
class LoadedFinancialSchemaBundle:
    """已加载的金融 schema bundle。"""

    manifest: BundleManifest
    objects_by_id: Dict[str, FinancialSchemaObject]
    objects_by_type: Dict[str, List[FinancialSchemaObject]]

    @property
    def bundle_id(self) -> str:
        return self.manifest.bundle_id

    @property
    def object_count(self) -> int:
        return len(self.objects_by_id)

    def get_object(self, object_id: str) -> Optional[FinancialSchemaObject]:
        return self.objects_by_id.get(object_id)
