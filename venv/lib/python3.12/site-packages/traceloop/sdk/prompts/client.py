from typing import Optional
from jinja2 import Environment, meta
from traceloop.sdk import Telemetry
from traceloop.sdk.prompts.model import Prompt, PromptVersion, TemplateEngine
from traceloop.sdk.prompts.registry import PromptRegistry
from traceloop.sdk.tracing.tracing import set_managed_prompt_tracing_context


def get_effective_version(prompt: Prompt) -> PromptVersion:
    if len(prompt.versions) == 0:
        raise Exception(f"No versions exist for {prompt.key} prompt")

    return next(v for v in prompt.versions if v.id == prompt.target.version)


def get_version_by_name(prompt: Prompt, name: str) -> PromptVersion:
    if len(prompt.versions) == 0:
        raise Exception(f"No versions exist for {prompt.key} prompt")

    return next(v for v in prompt.versions if v.name == name)


def get_version_by_hash(prompt: Prompt, hash: str) -> PromptVersion:
    if len(prompt.versions) == 0:
        raise Exception(f"No versions exist for {prompt.key} prompt")

    return next(v for v in prompt.versions if v.hash == hash)


def get_specific_version(prompt: Prompt, version: int) -> PromptVersion:
    if len(prompt.versions) == 0:
        raise Exception(f"No versions exist for {prompt.key} prompt")

    return next(v for v in prompt.versions if v.version == version)


class PromptRegistryClient:
    _registry: PromptRegistry
    _jinja_env: Environment

    def __new__(cls) -> "PromptRegistryClient":
        if not hasattr(cls, "instance"):
            obj = cls.instance = super(PromptRegistryClient, cls).__new__(cls)
            obj._registry = PromptRegistry()
            obj._jinja_env = Environment()

        return cls.instance

    def render_prompt(
        self,
        key: str,
        version: Optional[int] = None,
        version_name: Optional[str] = None,
        version_hash: Optional[str] = None,
        variables: dict = {},
    ):
        Telemetry().capture("prompt:rendered")

        prompt = self._registry.get_prompt_by_key(key)
        if prompt is None:
            raise Exception(f"Prompt {key} does not exist")

        prompt_version = None
        try:
            if version is not None:
                prompt_version = get_specific_version(prompt, version)
            elif version_name is not None:
                prompt_version = get_version_by_name(prompt, version_name)
            elif version_hash is not None:
                prompt_version = get_version_by_hash(prompt, version_hash)
            else:
                prompt_version = get_effective_version(prompt)
        except StopIteration:
            raise Exception(
                f"Prompt {key} does not have an available version to render"
            )

        params_dict = {"messages": self.render_messages(prompt_version, **variables)}
        params_dict.update(
            (k, v) for k, v in iter(prompt_version.llm_config) if v not in [None, []]
        )
        params_dict.pop("mode")

        set_managed_prompt_tracing_context(
            prompt.key,
            prompt_version.version,
            prompt_version.name,
            prompt_version.hash,
            variables,
        )

        return params_dict

    def render_messages(self, prompt_version: PromptVersion, **args):
        if prompt_version.templating_engine == TemplateEngine.JINJA2:
            rendered_messages = []
            for msg in prompt_version.messages:
                if isinstance(msg.template, str):
                    template = self._jinja_env.from_string(msg.template)
                    template_variables = meta.find_undeclared_variables(
                        self._jinja_env.parse(msg.template)
                    )
                    missing_variables = template_variables.difference(set(args.keys()))
                    if missing_variables == set():
                        rendered_msg = template.render(args)
                    else:
                        raise Exception(
                            f"Input variables: {','.join(str(var) for var in missing_variables)} are missing"
                        )

                else:
                    rendered_msg = []
                    template_variables = []
                    for content in msg.template:
                        if content.type == "text":
                            template = self._jinja_env.from_string(content.text)
                            template_variables = meta.find_undeclared_variables(
                                self._jinja_env.parse(msg.template)
                            )
                            missing_variables = template_variables.difference(
                                set(args.keys())
                            )
                            if missing_variables != set():
                                raise Exception(
                                    f"Input variables: {','.join(str(var) for var in missing_variables)} are missing"
                                )

                            rendered_msg.append(
                                {
                                    "type": "text",
                                    "text": template.render(args),
                                }
                            )
                        elif content.type == "image_url":
                            rendered_msg.append(content.dict())

                rendered_messages.append({"role": msg.role, "content": rendered_msg})

            return rendered_messages
        else:
            raise Exception(
                f"Templating engine {prompt_version.templating_engine} is not supported"
            )
