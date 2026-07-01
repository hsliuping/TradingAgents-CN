from typing import Any
import logging

from core.embedded_nanobot.agent.tools.base import Tool

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def get_definitions(self) -> list[dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> Any:
        hint = "\n\n[Analyze the error above and try a different approach.]"
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found. Available: {', '.join(self.tool_names)}"
        try:
            params = tool.cast_params(params)
            errors = tool.validate_params(params)
            if errors:
                logger.warning("[ToolRegistry][ValidationError] tool=%s errors=%s params=%s", name, errors, params)
                return f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors) + hint
            result = await tool.execute(**params)
            if isinstance(result, str) and result.startswith("Error"):
                logger.warning("[ToolRegistry][ToolErrorResult] tool=%s result=%s", name, result[:1000])
                return result + hint
            logger.info("[ToolRegistry][ToolSuccess] tool=%s result_chars=%d", name, len(str(result or "")))
            return result
        except Exception as exc:
            logger.exception("[ToolRegistry][Exception] tool=%s params=%s", name, params)
            return f"Error executing {name}: {exc}" + hint

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())