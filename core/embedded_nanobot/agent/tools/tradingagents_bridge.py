from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable

from core.embedded_nanobot.agent.tools.base import Tool
from core.tools.config import ToolMetadata, ToolParameter


def build_tool_schema(parameters: list[ToolParameter]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []

    for parameter in parameters or []:
        prop: dict[str, Any] = {
            "type": parameter.type or "string",
            "description": parameter.description or parameter.name,
        }
        if parameter.enum:
            prop["enum"] = list(parameter.enum)
        if parameter.default is not None:
            prop["default"] = parameter.default
        properties[parameter.name] = prop
        if parameter.required:
            required.append(parameter.name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


class TradingAgentsRegistryTool(Tool):
    def __init__(self, metadata: ToolMetadata, func: Callable[..., Any]):
        self.metadata = metadata
        self.func = func
        self._schema = build_tool_schema(list(metadata.parameters or []))

    @property
    def name(self) -> str:
        return self.metadata.id

    @property
    def description(self) -> str:
        return self.metadata.description or self.metadata.name or self.metadata.id

    @property
    def parameters(self) -> dict[str, Any]:
        return self._schema

    async def execute(self, **kwargs: Any) -> Any:
        target = self.func
        if hasattr(target, "ainvoke") and callable(target.ainvoke):
            return await target.ainvoke(kwargs)
        if hasattr(target, "invoke") and callable(target.invoke):
            return await asyncio.to_thread(target.invoke, kwargs)
        if hasattr(target, "arun") and callable(target.arun):
            return await target.arun(**kwargs)
        if hasattr(target, "run") and callable(target.run):
            return await asyncio.to_thread(target.run, kwargs)
        if inspect.iscoroutinefunction(target):
            return await target(**kwargs)
        return await asyncio.to_thread(target, **kwargs)


__all__ = ["TradingAgentsRegistryTool", "build_tool_schema"]