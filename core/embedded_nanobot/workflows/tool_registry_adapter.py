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
    """包装 ToolMetadata，提供 to_schema() 和 func 属性。"""

    def __init__(self, metadata: Any, executor: Any = None):
        self._metadata = metadata
        self._executor = executor  # StandardToolRegistryAdapter 引用，用于执行工具
        self.name = metadata.id

    # func 属性供 agent_builder_nodes.py 的 _run_node_llm_fc 使用，
    # 它在 wrapper 上查找 func/execute/run/handler 属性来执行工具。
    @property
    def func(self):
        if not self._executor:
            return None
        # 返回一个 async callable，签名为(**kwargs) -> str
        async def _execute(**kwargs):
            return await self._executor.execute(self.name, kwargs)
        return _execute

    def to_schema(self) -> dict[str, Any]:
        raw_params = self._metadata.parameters
        # 必须转成 OpenAI Function Calling 要求的 JSON Schema 对象格式：
        # {"type": "object", "properties": {...}, "required": [...]}
        if raw_params:
            properties = {}
            required = []
            for p in raw_params:
                if hasattr(p, "model_dump"):
                    d = p.model_dump(mode="json", exclude_none=True)
                elif hasattr(p, "dict"):
                    d = p.dict()
                elif isinstance(p, dict):
                    d = p
                else:
                    continue
                name = d.pop("name", None)
                if not name:
                    continue
                if d.pop("required", False):
                    required.append(name)
                properties[name] = d
            params_payload = {"type": "object", "properties": properties}
            if required:
                params_payload["required"] = required
            # 也保留原始数组格式给可能直接遍历参数的旧代码
            params_payload["__raw_params__"] = [
                dict(name=name, **prop) for name, prop in properties.items()
            ]
        else:
            params_payload = {"type": "object", "properties": {}}
        return {
            "name": self._metadata.id,
            "description": self._metadata.description or self._metadata.name,
            "parameters": params_payload,
        }


class StandardToolRegistryAdapter:
    """适配器：core.tools.registry → ToolRegistry 接口。"""

    def __init__(self):
        from core.tools import get_tool_registry
        self._registry = get_tool_registry()
        self._metadata_map: dict[str, Any] = {}
        for meta in self._registry.list_all():
            if meta.fc_enabled:
                self._metadata_map[meta.id] = meta

    def get(self, name: str) -> _ToolMetadataWrapper | None:
        meta = self._metadata_map.get(name)
        return _ToolMetadataWrapper(meta, executor=self) if meta else None

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
