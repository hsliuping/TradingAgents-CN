from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BaseMessage:
    role: str
    content: str

    def pretty_print(self) -> None:
        print(f"[{self.role}] {self.content}")


@dataclass
class HumanMessage(BaseMessage):
    role: str = field(default="user", init=False)


@dataclass
class SystemMessage(BaseMessage):
    role: str = field(default="system", init=False)


@dataclass
class AIMessage(BaseMessage):
    role: str = field(default="assistant", init=False)
    tool_calls: Optional[List[Dict[str, Any]]] = None


@dataclass
class ToolMessage(BaseMessage):
    role: str = field(default="tool", init=False)
    tool_call_id: Optional[str] = None


def to_openai_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for m in messages:
        item: Dict[str, Any] = {"role": m.role, "content": m.content}
        if isinstance(m, AIMessage) and m.tool_calls:
            item["tool_calls"] = m.tool_calls
        if isinstance(m, ToolMessage) and m.tool_call_id:
            item["tool_call_id"] = m.tool_call_id
        result.append(item)
    return result


def from_openai_message_dict(message: Dict[str, Any]) -> BaseMessage:
    role = message.get("role", "assistant")
    content = message.get("content", "")
    if role == "user":
        return HumanMessage(content=content)
    if role == "system":
        return SystemMessage(content=content)
    if role == "tool":
        return ToolMessage(content=content, tool_call_id=message.get("tool_call_id"))
    return AIMessage(content=content, tool_calls=message.get("tool_calls"))
