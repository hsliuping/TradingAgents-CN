import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class RegisteredTool:
    name: str
    func: Callable[..., Any]
    description: Optional[str] = None

    def __call__(self, **kwargs) -> Any:
        return self.func(**kwargs)


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, RegisteredTool] = {}

    def register(self, description: str = None):
        def decorator(func: Callable[..., Any]):
            name = func.__name__
            self._tools[name] = RegisteredTool(name=name, func=func, description=description)
            return func

        return decorator

    def register_function(self, func: Callable[..., Any], description: str = None):
        name = func.__name__
        self._tools[name] = RegisteredTool(name=name, func=func, description=description)

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = []
        for tool in self._tools.values():
            sig = inspect.signature(tool.func)
            properties: Dict[str, Any] = {}
            required: List[str] = []
            for param in sig.parameters.values():
                ptype = "string"
                if param.annotation in (int, "int"):
                    ptype = "integer"
                elif param.annotation in (float, "float"):
                    ptype = "number"
                elif param.annotation in (bool, "bool"):
                    ptype = "boolean"
                properties[param.name] = {"type": ptype}
                if param.default is inspect._empty:
                    required.append(param.name)

            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required,
                        },
                    },
                }
            )
        return tools

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        tool = self._tools.get(tool_name)
        if not tool:
            return {"error": f"tool not found: {tool_name}"}
        result = tool(**arguments)
        return {"output": result}


# Singleton instance for simple usage
registry = ToolRegistry()
