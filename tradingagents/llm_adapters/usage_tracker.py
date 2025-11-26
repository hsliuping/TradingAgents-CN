from dataclasses import dataclass
from typing import Any


@dataclass
class UsageInfo:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float = 0.0


class UsageExtractor:
    @staticmethod
    def from_openai(response: Any) -> UsageInfo:
        usage = getattr(response, "usage", None) or {}
        prompt = getattr(usage, "prompt_tokens", usage.get("prompt_tokens", 0))
        completion = getattr(usage, "completion_tokens", usage.get("completion_tokens", 0))
        total = getattr(usage, "total_tokens", usage.get("total_tokens", prompt + completion))
        return UsageInfo(input_tokens=int(prompt or 0), output_tokens=int(completion or 0),
                         total_tokens=int(total or 0))

    @staticmethod
    def from_google(response: Any) -> UsageInfo:
        usage = getattr(response, "usage_metadata", None)
        prompt = getattr(usage, "prompt_token_count", 0) if usage else 0
        completion = getattr(usage, "candidates_token_count", 0) if usage else 0
        total = getattr(usage, "total_token_count", prompt + completion) if usage else prompt + completion
        return UsageInfo(input_tokens=int(prompt), output_tokens=int(completion), total_tokens=int(total))
