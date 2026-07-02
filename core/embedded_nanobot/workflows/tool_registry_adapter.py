"""适配器：让 core.tools.registry 提供 Nanobot ToolRegistry 的接口。

LangGraph 节点（agent_builder_nodes.py）需要 tool_registry.get(name).to_schema()
和 tool_registry.execute(name, params) 接口。本适配器包装 core.tools.registry 提供相同接口。
"""
from __future__ import annotations

import inspect
import logging
from typing import Any

logger = logging.getLogger(__name__)


class _ToolMetadataWrapper:
    """包装 ToolMetadata，提供 to_schema() 方法。"""

    def __init__(self, metadata: Any):
        self._metadata = metadata
        self.name = metadata.id

    def to_schema(self) -> dict[str, Any]:
        return {
            "name": self._metadata.id,
            "description": self._metadata.description or self._metadata.name,
            "parameters": self._metadata.parameters or {"type": "object", "properties": {}},
        }


class StandardToolRegistryAdapter:
    """适配器：core.tools.registry → Nanobot ToolRegistry 接口。"""

    def __init__(self):
        from core.tools import get_tool_registry
        self._registry = get_tool_registry()
        self._metadata_map: dict[str, Any] = {}
        for meta in self._registry.list_all():
            if meta.fc_enabled:
                self._metadata_map[meta.id] = meta

    def get(self, name: str) -> _ToolMetadataWrapper | None:
        meta = self._metadata_map.get(name)
        return _ToolMetadataWrapper(meta) if meta else None

    def has(self, name: str) -> bool:
        return name in self._metadata_map

    async def execute(self, name: str, params: dict[str, Any]) -> str:
        func = self._registry.get_function(name)
        if not func:
            available = ", ".join(self._metadata_map.keys())
            return f"Error: Tool '{name}' not found. Available: {available}"
        try:
            # core.tools.registry 注册的函数可能是同步（def）或异步（async def），
            # 先调用，若返回 coroutine 再 await，兼容两种情况。
            result = func(**params)
            if inspect.isawaitable(result):
                result = await result
            result_str = str(result) if not isinstance(result, str) else result
            logger.info("[ToolAdapter][Success] tool=%s result_chars=%d", name, len(result_str))
            return result_str
        except Exception as exc:
            logger.exception("[ToolAdapter][Exception] tool=%s params=%s", name, params)
            return f"Error executing {name}: {exc}"

    @property
    def tool_names(self) -> list[str]:
        return list(self._metadata_map.keys())

    def get_definitions(self) -> list[dict[str, Any]]:
        return [self.get(name).to_schema() for name in self._metadata_map]  # type: ignore[union-attr]
