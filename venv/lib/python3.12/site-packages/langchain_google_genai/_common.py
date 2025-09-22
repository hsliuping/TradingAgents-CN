import os
from importlib import metadata
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from google.api_core.gapic_v1.client_info import ClientInfo
from langchain_core.utils import secret_from_env
from pydantic import BaseModel, Field, SecretStr

from langchain_google_genai._enums import HarmBlockThreshold, HarmCategory, Modality

_TELEMETRY_TAG = "remote_reasoning_engine"
_TELEMETRY_ENV_VARIABLE_NAME = "GOOGLE_CLOUD_AGENT_ENGINE_ID"


class GoogleGenerativeAIError(Exception):
    """
    Custom exception class for errors associated with the `Google GenAI` API.
    """


class _BaseGoogleGenerativeAI(BaseModel):
    """Base class for Google Generative AI LLMs"""

    model: str = Field(
        ...,
        description="""The name of the model to use.
Supported examples:
    - gemini-pro
    - models/text-bison-001""",
    )
    """Model name to use."""
    google_api_key: Optional[SecretStr] = Field(
        alias="api_key", default_factory=secret_from_env("GOOGLE_API_KEY", default=None)
    )
    """Google AI API key.
    If not specified will be read from env var ``GOOGLE_API_KEY``."""
    credentials: Any = None
    "The default custom credentials (google.auth.credentials.Credentials) to use "
    "when making API calls. If not provided, credentials will be ascertained from "
    "the GOOGLE_API_KEY envvar"
    temperature: float = 0.7
    """Run inference with this temperature. Must be within ``[0.0, 2.0]``."""
    top_p: Optional[float] = None
    """Decode using nucleus sampling: consider the smallest set of tokens whose
       probability sum is at least ``top_p``. Must be within ``[0.0, 1.0]``."""
    top_k: Optional[int] = None
    """Decode using top-k sampling: consider the set of ``top_k`` most probable tokens.
       Must be positive."""
    max_output_tokens: Optional[int] = Field(default=None, alias="max_tokens")
    """Maximum number of tokens to include in a candidate. Must be greater than zero.
       If unset, will default to ``64``."""
    n: int = 1
    """Number of chat completions to generate for each prompt. Note that the API may
       not return the full ``n`` completions if duplicates are generated."""
    max_retries: int = 6
    """The maximum number of retries to make when generating."""

    timeout: Optional[float] = None
    """The maximum number of seconds to wait for a response."""

    client_options: Optional[Dict] = Field(
        default=None,
        description=(
            "A dictionary of client options to pass to the Google API client, "
            "such as `api_endpoint`."
        ),
    )
    transport: Optional[str] = Field(
        default=None,
        description="A string, one of: [`rest`, `grpc`, `grpc_asyncio`].",
    )
    additional_headers: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "A key-value dictionary representing additional headers for the model call"
        ),
    )
    response_modalities: Optional[List[Modality]] = Field(
        default=None, description=("A list of modalities of the response")
    )

    thinking_budget: Optional[int] = Field(
        default=None, description="Indicates the thinking budget in tokens."
    )

    include_thoughts: Optional[bool] = Field(
        default=None,
        description="Indicates whether to include thoughts in the response.",
    )

    safety_settings: Optional[Dict[HarmCategory, HarmBlockThreshold]] = None
    """The default safety settings to use for all generations. 
    
        For example: 

        .. code-block:: python
            from google.generativeai.types.safety_types import HarmBlockThreshold, HarmCategory

            safety_settings = {
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            }
    """  # noqa: E501

    @property
    def lc_secrets(self) -> Dict[str, str]:
        return {"google_api_key": "GOOGLE_API_KEY"}

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get the identifying parameters."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_output_tokens": self.max_output_tokens,
            "candidate_count": self.n,
        }


def get_user_agent(module: Optional[str] = None) -> Tuple[str, str]:
    r"""Returns a custom user agent header.

    Args:
        module (Optional[str]):
            Optional. The module for a custom user agent header.
    Returns:
        Tuple[str, str]
    """
    try:
        langchain_version = metadata.version("langchain-google-genai")
    except metadata.PackageNotFoundError:
        langchain_version = "0.0.0"
    client_library_version = (
        f"{langchain_version}-{module}" if module else langchain_version
    )
    if os.environ.get(_TELEMETRY_ENV_VARIABLE_NAME):
        client_library_version += f"+{_TELEMETRY_TAG}"
    return client_library_version, f"langchain-google-genai/{client_library_version}"


def get_client_info(module: Optional[str] = None) -> "ClientInfo":
    r"""Returns a client info object with a custom user agent header.

    Args:
        module (Optional[str]):
            Optional. The module for a custom user agent header.
    Returns:
        ``google.api_core.gapic_v1.client_info.ClientInfo``
    """
    client_library_version, user_agent = get_user_agent(module)
    return ClientInfo(
        client_library_version=client_library_version,
        user_agent=user_agent,
    )


class SafetySettingDict(TypedDict):
    category: HarmCategory
    threshold: HarmBlockThreshold
