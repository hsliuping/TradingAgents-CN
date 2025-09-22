import typing

from traceloop.sdk.prompts.model import Prompt


class PromptRegistry:
    def __init__(self):
        self._prompts: typing.Dict[str, Prompt] = dict()

    def get_prompt_by_key(self, key):
        return self._prompts.get(key, None)

    def load(self, prompts_json: dict):
        for prompt_obj in prompts_json["prompts"]:
            self._prompts[prompt_obj["key"]] = Prompt(**prompt_obj)
