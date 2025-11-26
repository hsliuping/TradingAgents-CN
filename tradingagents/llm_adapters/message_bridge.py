from typing import Dict, List

from .local_messages import BaseMessage, HumanMessage, AIMessage, to_openai_messages, \
    from_openai_message_dict


def langchain_to_openai(messages: List[BaseMessage]) -> List[Dict]:
    return to_openai_messages(messages)


def openai_to_langchain(messages: List[Dict]) -> List[BaseMessage]:
    return [from_openai_message_dict(m) for m in messages]


def create_user_message(content: str) -> HumanMessage:
    return HumanMessage(content=content)


def create_ai_message(content: str, tool_calls: List[Dict] = None) -> AIMessage:
    return AIMessage(content=content, tool_calls=tool_calls)
