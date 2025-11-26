import google.generativeai as genai
from openai import OpenAI
from typing import Any, Dict, List, Optional

from .local_messages import AIMessage, BaseMessage
from .local_messages import to_openai_messages, from_openai_message_dict


class UnifiedOpenAIClient:
    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None, **kwargs):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.config = kwargs

    def invoke(self, messages: List[BaseMessage]) -> AIMessage:
        payload = to_openai_messages(messages)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=payload,
            **self.config,
        )
        msg = response.choices[0].message
        content = msg.content or ""
        tool_calls = []
        if getattr(msg, "tool_calls", None):
            # Convert OpenAI tool_calls objects to plain dicts
            for tc in msg.tool_calls:
                fn = getattr(tc, "function", None)
                args = getattr(fn, "arguments", "{}") if fn else "{}"
                tool_calls.append({
                    "id": getattr(tc, "id", None),
                    "name": getattr(fn, "name", None) if fn else None,
                    "args": args,
                })
        return AIMessage(content=content, tool_calls=tool_calls)


class GoogleGeminiClient:
    def __init__(self, model: str, api_key: str, **kwargs):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self.config = kwargs

    def invoke(self, messages: List[BaseMessage]) -> AIMessage:
        # Concatenate messages into a single prompt; simple compatibility
        text = "\n\n".join(m.content for m in messages)
        response = self.model.generate_content(text, **self.config)
        content = getattr(response, "text", None) or ""
        return AIMessage(content=content, tool_calls=[])


class AnthropicClient:
    def __init__(self, model: str, api_key: str, **kwargs):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.config = kwargs

    def invoke(self, messages: List[BaseMessage]) -> AIMessage:
        payload = [from_openai_message_dict({"role": m.role, "content": m.content}) for m in messages]
        # Convert to Anthropic style
        response = self.client.messages.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            **self.config,
        )
        # Extract first text content
        content = ""
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "text":
                content = getattr(block, "text", "")
                break
        return AIMessage(content=content, tool_calls=[])
