import os
from typing import Any, Optional

from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langchain_openai.chat_models.base import (
    _convert_message_to_dict,
    _convert_from_v1_to_chat_completions,
)
import openai

from .base_client import BaseLLMClient, normalize_content
from .validators import validate_model


class NormalizedChatOpenAI(ChatOpenAI):
    """ChatOpenAI wrapper that normalizes typed content blocks to text.

    Also preserves DeepSeek `reasoning_content` across multi-turn conversations.
    DeepSeek's deepseek-reasoner returns `reasoning_content` in responses; LangChain's
    _convert_dict_to_message silently drops it. On subsequent requests, the API
    re-checks and rejects assistant messages missing `reasoning_content` with:
        'The reasoning_content in the thinking mode must be passed back to the API.'

    This class:
    - Captures `reasoning_content` from responses and stores it in additional_kwargs
    - Includes `reasoning_content` back in request payloads for multi-turn history
    """

    def invoke(self, input, config=None, **kwargs):
        return normalize_content(super().invoke(input, config, **kwargs))

    def _create_chat_result(
        self,
        response: dict | openai.BaseModel,
        generation_info: dict | None = None,
    ) -> Any:
        """Override to capture reasoning_content from DeepSeek responses.

        LangChain's _convert_dict_to_message silently drops the `reasoning_content`
        field from DeepSeek's response. We need to preserve it so it can be passed
        back on subsequent requests.
        """
        # Get the response dict
        response_dict = (
            response if isinstance(response, dict) else response.model_dump()
        )

        # Extract reasoning_content from the raw response before it gets dropped
        reasoning_content = None
        choices = response_dict.get("choices", [])
        if choices and isinstance(choices, list) and len(choices) > 0:
            message_dict = choices[0].get("message", {})
            reasoning_content = message_dict.get("reasoning_content")

        # Call parent's method to create the ChatResult
        result = super()._create_chat_result(response, generation_info)

        # Inject reasoning_content into the AIMessage's additional_kwargs
        if reasoning_content and result.generations:
            msg = result.generations[0].message
            if isinstance(msg, AIMessage):
                msg.additional_kwargs["reasoning_content"] = reasoning_content

        return result

    def _get_request_payload(self, input_, stop=None, **kwargs):
        """Override to include reasoning_content from additional_kwargs in message dicts.

        LangChain's _convert_message_to_dict doesn't include additional_kwargs entries
        like reasoning_content. DeepSeek requires it for multi-turn deepseek-reasoner.
        """
        messages = self._convert_input(input_).to_messages()
        if stop is not None:
            kwargs["stop"] = stop

        payload = {**self._default_params, **kwargs}

        if self._use_responses_api(payload):
            if self.use_previous_response_id:
                from langchain_openai.chat_models.base import (  # noqa: PLC0415
                    _get_last_messages,
                    _construct_responses_api_payload,
                )

                last_messages, previous_response_id = _get_last_messages(messages)
                payload_to_use = last_messages if previous_response_id else messages
                if previous_response_id:
                    payload["previous_response_id"] = previous_response_id
                payload = _construct_responses_api_payload(payload_to_use, payload)
            else:
                from langchain_openai.chat_models.base import (  # noqa: PLC0415
                    _construct_responses_api_payload,
                )

                payload = _construct_responses_api_payload(messages, payload)
        else:
            payload["messages"] = [
                _convert_message_to_dict(
                    _convert_from_v1_to_chat_completions(m)
                    if isinstance(m, AIMessage)
                    else m
                )
                for m in messages
            ]

        # Inject reasoning_content from additional_kwargs into serialized message dicts
        for msg, msg_dict in zip(messages, payload.get("messages", [])):
            if (
                isinstance(msg, AIMessage)
                and msg_dict.get("role") == "assistant"
                and "reasoning_content" in msg.additional_kwargs
            ):
                msg_dict["reasoning_content"] = msg.additional_kwargs["reasoning_content"]

        return payload


_PASSTHROUGH_KWARGS = (
    "temperature",
    "max_tokens",
    "timeout",
    "max_retries",
    "callbacks",
    "http_client",
    "http_async_client",
)

_PROVIDER_CONFIG = {
    "deepseek": ("https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    "qwen": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY"),
    "glm": ("https://open.bigmodel.cn/api/paas/v4/", "ZHIPU_API_KEY"),
    "qianfan": ("https://qianfan.baiduce.com/v2", "QIANFAN_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "aihubmix": ("https://aihubmix.com/v1", "AIHUBMIX_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
    "custom_openai": (None, "CUSTOM_OPENAI_API_KEY"),
}


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI and OpenAI-compatible providers."""

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        provider: str = "openai",
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)
        self.provider = provider.lower()

    def get_llm(self) -> Any:
        self.warn_if_unknown_model()
        llm_kwargs = {"model": self.model}

        if self.provider in _PROVIDER_CONFIG:
            default_base_url, api_key_env = _PROVIDER_CONFIG[self.provider]
            llm_kwargs["base_url"] = self.base_url or default_base_url
            if api_key_env:
                api_key = self.kwargs.get("api_key") or os.environ.get(api_key_env)
                if api_key:
                    llm_kwargs["api_key"] = api_key
            else:
                llm_kwargs["api_key"] = "ollama"
        elif self.base_url:
            llm_kwargs["base_url"] = self.base_url
            api_key = self.kwargs.get("api_key") or os.environ.get("OPENAI_API_KEY")
            if api_key:
                llm_kwargs["api_key"] = api_key

        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        return NormalizedChatOpenAI(**llm_kwargs)

    def validate_model(self) -> bool:
        return validate_model(self.provider, self.model)
