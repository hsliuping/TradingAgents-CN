"""数据能力注册表（CapabilityRegistry）

数据源以声明式装饰器把已有实现挂载为"数据能力"，实现零改动：
现有 provider 方法不动，只加 @register_capability 声明。

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .schema import CapabilitySchema
from .schemas import get_schema

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CapabilityEntry:
    """单个 (能力, 数据源) 的注册项"""
    capability_id: str
    source: str
    func: Callable[..., Any]        # 数据源实现（provider 方法，首参为 self）
    field_mapping: Dict[str, str]   # 原始字段名 -> 标准字段名
    schema: CapabilitySchema
    provider_factory: Optional[Callable[[], Any]] = None  # 取 provider 实例；None 时门面按 source 解析


class CapabilityRegistry:
    """能力注册表：capability_id -> source -> CapabilityEntry"""

    def __init__(self):
        self._entries: Dict[str, Dict[str, CapabilityEntry]] = {}

    def register(self, entry: CapabilityEntry) -> None:
        sources = self._entries.setdefault(entry.capability_id, {})
        if entry.source in sources:
            raise ValueError(
                f"能力 '{entry.capability_id}' 的数据源 '{entry.source}' 重复注册"
            )
        sources[entry.source] = entry
        logger.info(
            "已注册数据能力: %s <- %s（映射 %d 个字段）",
            entry.capability_id, entry.source, len(entry.field_mapping),
        )

    def get_sources(self, capability_id: str) -> List[str]:
        """返回该能力已注册的数据源列表（注册顺序）"""
        return list(self._entries.get(capability_id, {}))

    def get_entry(self, capability_id: str, source: str) -> CapabilityEntry:
        try:
            return self._entries[capability_id][source]
        except KeyError:
            raise ValueError(
                f"能力 '{capability_id}' 未注册数据源 '{source}'"
            ) from None

    def list_capabilities(self) -> List[str]:
        return list(self._entries)


# 全局注册表
registry = CapabilityRegistry()


def register_capability(
    capability_id: str,
    source: str,
    field_mapping: Dict[str, str],
    grain: str = None,
    provider_factory: Callable[[], Any] = None,
):
    """
    数据能力注册装饰器（声明式挂载，数据源实现零改动）。

    挂载时强制校验：
    1. capability_id 必须已有标准 Schema（schemas/ 中定义）
    2. field_mapping 的目标字段必须都在 Schema 标准字段集合内
    3. 若声明 grain，必须与 Schema 的 grain 一致——
       粒度不同的数据源不允许注册到同一能力（防降级语义漂移）

    Args:
        capability_id: 能力 ID，如 'margin'
        source: 数据源编码，如 'tushare' / 'akshare'
        field_mapping: 原始字段名 -> 标准字段名（只列需要映射的列）
        grain: 粒度声明（可选，给出时必须与 Schema 一致）
        provider_factory: 取 provider 实例的工厂（可选，
            缺省由门面按 source 解析内置 provider）
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        registry.register(CapabilityEntry(
            capability_id=capability_id,
            source=source,
            func=func,
            field_mapping=dict(field_mapping),
            schema=schema,
            provider_factory=provider_factory,
        ))
        return func  # 不包装函数，现有实现语义零改动

    # 校验放在工厂调用时（fail-fast）：声明写错立即报错，而非等到装饰应用时
    schema = get_schema(capability_id)

    if grain is not None and grain != schema.grain:
        raise ValueError(
            f"能力 '{capability_id}' 的粒度是 '{schema.grain}'，"
            f"但数据源 '{source}' 声明为 '{grain}'。"
            f"粒度不同的数据不允许注册到同一能力，请另立能力 ID。"
        )

    schema.validate_field_mapping(field_mapping)

    return decorator
