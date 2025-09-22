import logging
from typing import TYPE_CHECKING, Callable, Optional, TypedDict

from literalai.cache.prompt_helpers import put_prompt
from literalai.observability.generation import GenerationMessage
from literalai.prompt_engineering.prompt import Prompt, ProviderSettings

if TYPE_CHECKING:
    from literalai.api import LiteralAPI
    from literalai.cache.shared_cache import SharedCache

from literalai.api.helpers import gql

logger = logging.getLogger(__name__)


def create_prompt_lineage_helper(name: str, description: Optional[str] = None):
    variables = {"name": name, "description": description}

    def process_response(response):
        prompt = response["data"]["createPromptLineage"]
        if prompt and prompt.get("deletedAt"):
            logger.warning(
                f"Prompt {name} was deleted - please update any references to use an active prompt in production"
            )
        return prompt

    description = "create prompt lineage"

    return gql.CREATE_PROMPT_LINEAGE, description, variables, process_response


def get_prompt_lineage_helper(name: str):
    variables = {"name": name}

    def process_response(response):
        prompt = response["data"]["promptLineage"]
        if prompt and prompt.get("deletedAt"):
            logger.warning(
                f"Prompt {name} was deleted - please update any references to use an active prompt in production"
            )
        return prompt

    description = "get prompt lineage"

    return gql.GET_PROMPT_LINEAGE, description, variables, process_response


def create_prompt_helper(
    api: "LiteralAPI",
    lineage_id: str,
    template_messages: list[GenerationMessage],
    settings: Optional[ProviderSettings] = None,
    tools: Optional[list[dict]] = None,
):
    variables = {
        "lineageId": lineage_id,
        "templateMessages": template_messages,
        "settings": settings,
        "tools": tools,
    }

    def process_response(response):
        prompt = response["data"]["createPromptVersion"]
        prompt_lineage = prompt.get("lineage")

        if prompt_lineage and prompt_lineage.get("deletedAt"):
            logger.warning(
                f"Prompt {prompt_lineage.get('name')} was deleted - please update any references to use an active prompt in production"
            )
        return Prompt.from_dict(api, prompt) if prompt else None

    description = "create prompt version"

    return gql.CREATE_PROMPT_VERSION, description, variables, process_response


def get_prompt_cache_key(
    id: Optional[str], name: Optional[str], version: Optional[int]
) -> str:
    if id:
        return id
    elif name and version:
        return f"{name}-{version}"
    elif name:
        return name
    else:
        raise ValueError("Either the `id` or the `name` must be provided.")


def get_prompt_helper(
    api: "LiteralAPI",
    id: Optional[str] = None,
    name: Optional[str] = None,
    version: Optional[int] = 0,
    cache: Optional["SharedCache"] = None,
) -> tuple[str, str, dict, Callable, int, Optional[Prompt]]:
    """Helper function for getting prompts with caching logic"""

    cached_prompt = None
    timeout = 10

    if cache:
        cached_prompt = cache.get(get_prompt_cache_key(id, name, version))
        timeout = 1 if cached_prompt else timeout

    variables = {"id": id, "name": name, "version": version}

    def process_response(response):
        prompt_version = response["data"]["promptVersion"]
        prompt_lineage = prompt_version.get("lineage")

        if prompt_lineage and prompt_lineage.get("deletedAt"):
            logger.warning(
                f"Prompt {name} was deleted - please update any references to use an active prompt in production"
            )
        prompt = Prompt.from_dict(api, prompt_version) if prompt_version else None
        if cache and prompt:
            put_prompt(cache, prompt)
        return prompt

    description = "get prompt"

    return (
        gql.GET_PROMPT_VERSION,
        description,
        variables,
        process_response,
        timeout,
        cached_prompt,
    )


def create_prompt_variant_helper(
    from_lineage_id: Optional[str] = None,
    template_messages: list[GenerationMessage] = [],
    settings: Optional[ProviderSettings] = None,
    tools: Optional[list[dict]] = None,
):
    variables = {
        "fromLineageId": from_lineage_id,
        "templateMessages": template_messages,
        "settings": settings,
        "tools": tools,
    }

    def process_response(response) -> Optional[str]:
        variant = response["data"]["createPromptExperiment"]
        return variant["id"] if variant else None

    description = "create prompt variant"

    return gql.CREATE_PROMPT_VARIANT, description, variables, process_response


class PromptRollout(TypedDict):
    version: int
    rollout: int


def get_prompt_ab_testing_helper(
    name: Optional[str] = None,
):
    variables = {"lineageName": name}

    def process_response(response) -> list[PromptRollout]:
        response_data = response["data"]["promptLineageRollout"]
        return list(map(lambda x: x["node"], response_data["edges"]))

    description = "get prompt A/B testing"

    return gql.GET_PROMPT_AB_TESTING, description, variables, process_response


def update_prompt_ab_testing_helper(name: str, rollouts: list[PromptRollout]):
    variables = {"name": name, "rollouts": rollouts}

    def process_response(response) -> dict:
        return response["data"]["updatePromptLineageRollout"]

    description = "update prompt A/B testing"

    return gql.UPDATE_PROMPT_AB_TESTING, description, variables, process_response
