from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from .local_messages import BaseMessage, HumanMessage, SystemMessage, AIMessage


@dataclass
class ChatPromptTemplate:
    system_template: Optional[str]
    messages_placeholder: Optional[str]

    @staticmethod
    def from_messages(spec: List[Tuple[str, str]]) -> "ChatPromptTemplate":
        system_msg: Optional[str] = None
        placeholder_name: Optional[str] = None
        for kind, value in spec:
            if kind == "system":
                system_msg = value
            elif kind == "messages_placeholder":
                placeholder_name = value
        return ChatPromptTemplate(system_template=system_msg, messages_placeholder=placeholder_name)

    def partial(self, **kwargs) -> "ChatPromptTemplate":
        rendered_system = self.system_template.format(**kwargs) if self.system_template else None
        return ChatPromptTemplate(system_template=rendered_system, messages_placeholder=self.messages_placeholder)

    def __or__(self, other: Any) -> "PromptLLMChain":
        return PromptLLMChain(prompt=self, llm=other)


class PromptLLMChain:
    def __init__(self, prompt: ChatPromptTemplate, llm: Any):
        self.prompt = prompt
        self.llm = llm

    def invoke(self, payload: Union[str, Dict[str, Any], List[BaseMessage]]) -> AIMessage:
        if isinstance(payload, str):
            messages: List[BaseMessage] = [HumanMessage(content=payload)]
        elif isinstance(payload, list):
            messages = payload  # type: ignore
        elif isinstance(payload, dict):
            key = self.prompt.messages_placeholder or "messages"
            messages = payload.get(key, [])  # type: ignore
        else:
            messages = []

        final_messages: List[BaseMessage] = []
        if self.prompt.system_template:
            final_messages.append(SystemMessage(content=self.prompt.system_template))
        final_messages.extend(messages)
        return self.llm.invoke(final_messages)
