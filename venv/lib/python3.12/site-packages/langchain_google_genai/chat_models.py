from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import mimetypes
import uuid
import warnings
import wave
from difflib import get_close_matches
from operator import itemgetter
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

import filetype  # type: ignore[import]
import google.api_core

# TODO: remove ignore once the Google package is published with types
import proto  # type: ignore[import]
from google.ai.generativelanguage_v1beta import (
    GenerativeServiceAsyncClient as v1betaGenerativeServiceAsyncClient,
)
from google.ai.generativelanguage_v1beta.types import (
    Blob,
    Candidate,
    CodeExecution,
    CodeExecutionResult,
    Content,
    ExecutableCode,
    FileData,
    FunctionCall,
    FunctionDeclaration,
    FunctionResponse,
    GenerateContentRequest,
    GenerateContentResponse,
    GenerationConfig,
    Part,
    SafetySetting,
    ToolConfig,
    VideoMetadata,
)
from google.ai.generativelanguage_v1beta.types import Tool as GoogleTool
from langchain_core.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.chat_models import BaseChatModel, LangSmithParams
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    is_data_content_block,
)
from langchain_core.messages.ai import UsageMetadata, add_usage, subtract_usage
from langchain_core.messages.tool import invalid_tool_call, tool_call, tool_call_chunk
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from langchain_core.output_parsers.base import OutputParserLike
from langchain_core.output_parsers.openai_tools import (
    JsonOutputKeyToolsParser,
    PydanticToolsParser,
    parse_tool_calls,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable, RunnableConfig, RunnablePassthrough
from langchain_core.tools import BaseTool
from langchain_core.utils import get_pydantic_field_names
from langchain_core.utils.function_calling import (
    convert_to_json_schema,
    convert_to_openai_tool,
)
from langchain_core.utils.pydantic import is_basemodel_subclass
from langchain_core.utils.utils import _build_model_kwargs
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)
from pydantic.v1 import BaseModel as BaseModelV1
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from typing_extensions import Self, is_typeddict

from langchain_google_genai._common import (
    GoogleGenerativeAIError,
    SafetySettingDict,
    _BaseGoogleGenerativeAI,
    get_client_info,
)
from langchain_google_genai._function_utils import (
    _dict_to_gapic_schema,
    _tool_choice_to_tool_config,
    _ToolChoiceType,
    _ToolConfigDict,
    _ToolDict,
    convert_to_genai_function_declarations,
    is_basemodel_subclass_safe,
    replace_defs_in_schema,
    tool_to_dict,
)
from langchain_google_genai._image_utils import (
    ImageBytesLoader,
    image_bytes_to_b64_string,
)

from . import _genai_extension as genaix

logger = logging.getLogger(__name__)

_allowed_params_prediction_service = ["request", "timeout", "metadata", "labels"]

_FunctionDeclarationType = Union[
    FunctionDeclaration,
    dict[str, Any],
    Callable[..., Any],
]


class ChatGoogleGenerativeAIError(GoogleGenerativeAIError):
    """
    Custom exception class for errors associated with the `Google GenAI` API.

    This exception is raised when there are specific issues related to the
    Google genai API usage in the ChatGoogleGenerativeAI class, such as unsupported
    message types or roles.
    """


def _create_retry_decorator() -> Callable[[Any], Any]:
    """
    Creates and returns a preconfigured tenacity retry decorator.

    The retry decorator is configured to handle specific Google API exceptions
    such as ResourceExhausted and ServiceUnavailable. It uses an exponential
    backoff strategy for retries.

    Returns:
        Callable[[Any], Any]: A retry decorator configured for handling specific
        Google API exceptions.
    """
    multiplier = 2
    min_seconds = 1
    max_seconds = 60
    max_retries = 2

    return retry(
        reraise=True,
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=multiplier, min=min_seconds, max=max_seconds),
        retry=(
            retry_if_exception_type(google.api_core.exceptions.ResourceExhausted)
            | retry_if_exception_type(google.api_core.exceptions.ServiceUnavailable)
            | retry_if_exception_type(google.api_core.exceptions.GoogleAPIError)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


def _chat_with_retry(generation_method: Callable, **kwargs: Any) -> Any:
    """
    Executes a chat generation method with retry logic using tenacity.

    This function is a wrapper that applies a retry mechanism to a provided
    chat generation function. It is useful for handling intermittent issues
    like network errors or temporary service unavailability.

    Args:
        generation_method (Callable): The chat generation method to be executed.
        **kwargs (Any): Additional keyword arguments to pass to the generation method.

    Returns:
        Any: The result from the chat generation method.
    """
    retry_decorator = _create_retry_decorator()

    @retry_decorator
    def _chat_with_retry(**kwargs: Any) -> Any:
        try:
            return generation_method(**kwargs)
        # Do not retry for these errors.
        except google.api_core.exceptions.FailedPrecondition as exc:
            if "location is not supported" in exc.message:
                error_msg = (
                    "Your location is not supported by google-generativeai "
                    "at the moment. Try to use ChatVertexAI LLM from "
                    "langchain_google_vertexai."
                )
                raise ValueError(error_msg)

        except google.api_core.exceptions.InvalidArgument as e:
            raise ChatGoogleGenerativeAIError(
                f"Invalid argument provided to Gemini: {e}"
            ) from e
        except Exception as e:
            raise e

    params = (
        {k: v for k, v in kwargs.items() if k in _allowed_params_prediction_service}
        if (request := kwargs.get("request"))
        and hasattr(request, "model")
        and "gemini" in request.model
        else kwargs
    )
    return _chat_with_retry(**params)


async def _achat_with_retry(generation_method: Callable, **kwargs: Any) -> Any:
    """
    Executes a chat generation method with retry logic using tenacity.

    This function is a wrapper that applies a retry mechanism to a provided
    chat generation function. It is useful for handling intermittent issues
    like network errors or temporary service unavailability.

    Args:
        generation_method (Callable): The chat generation method to be executed.
        **kwargs (Any): Additional keyword arguments to pass to the generation method.

    Returns:
        Any: The result from the chat generation method.
    """
    retry_decorator = _create_retry_decorator()
    from google.api_core.exceptions import InvalidArgument  # type: ignore

    @retry_decorator
    async def _achat_with_retry(**kwargs: Any) -> Any:
        try:
            return await generation_method(**kwargs)
        except InvalidArgument as e:
            # Do not retry for these errors.
            raise ChatGoogleGenerativeAIError(
                f"Invalid argument provided to Gemini: {e}"
            ) from e
        except Exception as e:
            raise e

    params = (
        {k: v for k, v in kwargs.items() if k in _allowed_params_prediction_service}
        if (request := kwargs.get("request"))
        and hasattr(request, "model")
        and "gemini" in request.model
        else kwargs
    )
    return await _achat_with_retry(**params)


def _is_lc_content_block(part: dict) -> bool:
    return "type" in part


def _is_openai_image_block(block: dict) -> bool:
    """Check if the block contains image data in OpenAI Chat Completions format."""
    if block.get("type") == "image_url":
        if (
            (set(block.keys()) <= {"type", "image_url", "detail"})
            and (image_url := block.get("image_url"))
            and isinstance(image_url, dict)
        ):
            url = image_url.get("url")
            if isinstance(url, str):
                return True
    else:
        return False

    return False


def _convert_to_parts(
    raw_content: Union[str, Sequence[Union[str, dict]]],
) -> List[Part]:
    """Converts a list of LangChain messages into a Google parts."""
    parts = []
    content = [raw_content] if isinstance(raw_content, str) else raw_content
    image_loader = ImageBytesLoader()
    for part in content:
        if isinstance(part, str):
            parts.append(Part(text=part))
        elif isinstance(part, Mapping):
            if _is_lc_content_block(part):
                if part["type"] == "text":
                    parts.append(Part(text=part["text"]))
                elif is_data_content_block(part):
                    if part["source_type"] == "url":
                        bytes_ = image_loader._bytes_from_url(part["url"])
                    elif part["source_type"] == "base64":
                        bytes_ = base64.b64decode(part["data"])
                    else:
                        raise ValueError("source_type must be url or base64.")
                    inline_data: dict = {"data": bytes_}
                    if "mime_type" in part:
                        inline_data["mime_type"] = part["mime_type"]
                    else:
                        source = cast(str, part.get("url") or part.get("data"))
                        mime_type, _ = mimetypes.guess_type(source)
                        if not mime_type:
                            kind = filetype.guess(bytes_)
                            if kind:
                                mime_type = kind.mime
                        if mime_type:
                            inline_data["mime_type"] = mime_type
                    parts.append(Part(inline_data=inline_data))
                elif part["type"] == "image_url":
                    img_url = part["image_url"]
                    if isinstance(img_url, dict):
                        if "url" not in img_url:
                            raise ValueError(
                                f"Unrecognized message image format: {img_url}"
                            )
                        img_url = img_url["url"]
                    parts.append(image_loader.load_part(img_url))
                # Handle media type like LangChain.js
                # https://github.com/langchain-ai/langchainjs/blob/e536593e2585f1dd7b0afc187de4d07cb40689ba/libs/langchain-google-common/src/utils/gemini.ts#L93-L106
                elif part["type"] == "media":
                    if "mime_type" not in part:
                        raise ValueError(f"Missing mime_type in media part: {part}")
                    mime_type = part["mime_type"]
                    media_part = Part()

                    if "data" in part:
                        media_part.inline_data = Blob(
                            data=part["data"], mime_type=mime_type
                        )
                    elif "file_uri" in part:
                        media_part.file_data = FileData(
                            file_uri=part["file_uri"], mime_type=mime_type
                        )
                    else:
                        raise ValueError(
                            f"Media part must have either data or file_uri: {part}"
                        )
                    if "video_metadata" in part:
                        metadata = VideoMetadata(part["video_metadata"])
                        media_part.video_metadata = metadata
                    parts.append(media_part)
                elif part["type"] == "executable_code":
                    if "executable_code" not in part or "language" not in part:
                        raise ValueError(
                            "Executable code part must have 'code' and 'language' "
                            f"keys, got {part}"
                        )
                    executable_code_part = Part(
                        executable_code=ExecutableCode(
                            language=part["language"], code=part["executable_code"]
                        )
                    )
                    parts.append(executable_code_part)
                elif part["type"] == "code_execution_result":
                    if "code_execution_result" not in part:
                        raise ValueError(
                            "Code execution result part must have "
                            f"'code_execution_result', got {part}"
                        )
                    if "outcome" in part:
                        outcome = part["outcome"]
                    else:
                        # Backward compatibility
                        outcome = 1  # Default to success if not specified
                    code_execution_result_part = Part(
                        code_execution_result=CodeExecutionResult(
                            output=part["code_execution_result"], outcome=outcome
                        )
                    )
                    parts.append(code_execution_result_part)
                elif part["type"] == "thinking":
                    parts.append(Part(text=part["thinking"], thought=True))
                else:
                    raise ValueError(
                        f"Unrecognized message part type: {part['type']}. Only text, "
                        f"image_url, and media types are supported."
                    )
            else:
                # Yolo
                logger.warning(
                    "Unrecognized message part format. Assuming it's a text part."
                )
                parts.append(Part(text=str(part)))
        else:
            # TODO: Maybe some of Google's native stuff
            # would hit this branch.
            raise ChatGoogleGenerativeAIError(
                "Gemini only supports text and inline_data parts."
            )
    return parts


def _convert_tool_message_to_parts(
    message: ToolMessage | FunctionMessage, name: Optional[str] = None
) -> list[Part]:
    """Converts a tool or function message to a Google part."""
    # Legacy agent stores tool name in message.additional_kwargs instead of message.name
    name = message.name or name or message.additional_kwargs.get("name")
    response: Any
    parts: list[Part] = []
    if isinstance(message.content, list):
        media_blocks = []
        other_blocks = []
        for block in message.content:
            if isinstance(block, dict) and (
                is_data_content_block(block) or _is_openai_image_block(block)
            ):
                media_blocks.append(block)
            else:
                other_blocks.append(block)
        parts.extend(_convert_to_parts(media_blocks))
        response = other_blocks

    elif not isinstance(message.content, str):
        response = message.content
    else:
        try:
            response = json.loads(message.content)
        except json.JSONDecodeError:
            response = message.content  # leave as str representation
    part = Part(
        function_response=FunctionResponse(
            name=name,
            response=(
                {"output": response} if not isinstance(response, dict) else response
            ),
        )
    )
    parts.append(part)
    return parts


def _get_ai_message_tool_messages_parts(
    tool_messages: Sequence[ToolMessage], ai_message: AIMessage
) -> list[Part]:
    """
    Finds relevant tool messages for the AI message and converts them to a single
    list of Parts.
    """
    # We are interested only in the tool messages that are part of the AI message
    tool_calls_ids = {tool_call["id"]: tool_call for tool_call in ai_message.tool_calls}
    parts = []
    for i, message in enumerate(tool_messages):
        if not tool_calls_ids:
            break
        if message.tool_call_id in tool_calls_ids:
            tool_call = tool_calls_ids[message.tool_call_id]
            message_parts = _convert_tool_message_to_parts(
                message, name=tool_call.get("name")
            )
            parts.extend(message_parts)
            # remove the id from the dict, so that we do not iterate over it again
            tool_calls_ids.pop(message.tool_call_id)
    return parts


def _parse_chat_history(
    input_messages: Sequence[BaseMessage], convert_system_message_to_human: bool = False
) -> Tuple[Optional[Content], List[Content]]:
    messages: List[Content] = []

    if convert_system_message_to_human:
        warnings.warn("Convert_system_message_to_human will be deprecated!")

    system_instruction: Optional[Content] = None
    messages_without_tool_messages = [
        message for message in input_messages if not isinstance(message, ToolMessage)
    ]
    tool_messages = [
        message for message in input_messages if isinstance(message, ToolMessage)
    ]
    for i, message in enumerate(messages_without_tool_messages):
        if isinstance(message, SystemMessage):
            system_parts = _convert_to_parts(message.content)
            if i == 0:
                system_instruction = Content(parts=system_parts)
            elif system_instruction is not None:
                system_instruction.parts.extend(system_parts)
            else:
                pass
            continue
        elif isinstance(message, AIMessage):
            role = "model"
            if message.tool_calls:
                ai_message_parts = []
                for tool_call in message.tool_calls:
                    function_call = FunctionCall(
                        {
                            "name": tool_call["name"],
                            "args": tool_call["args"],
                        }
                    )
                    ai_message_parts.append(Part(function_call=function_call))
                tool_messages_parts = _get_ai_message_tool_messages_parts(
                    tool_messages=tool_messages, ai_message=message
                )
                messages.append(Content(role=role, parts=ai_message_parts))
                messages.append(Content(role="user", parts=tool_messages_parts))
                continue
            elif raw_function_call := message.additional_kwargs.get("function_call"):
                function_call = FunctionCall(
                    {
                        "name": raw_function_call["name"],
                        "args": json.loads(raw_function_call["arguments"]),
                    }
                )
                parts = [Part(function_call=function_call)]
            else:
                parts = _convert_to_parts(message.content)
        elif isinstance(message, HumanMessage):
            role = "user"
            parts = _convert_to_parts(message.content)
            if i == 1 and convert_system_message_to_human and system_instruction:
                parts = [p for p in system_instruction.parts] + parts
                system_instruction = None
        elif isinstance(message, FunctionMessage):
            role = "user"
            parts = _convert_tool_message_to_parts(message)
        else:
            raise ValueError(
                f"Unexpected message with type {type(message)} at the position {i}."
            )

        messages.append(Content(role=role, parts=parts))
    return system_instruction, messages


# Helper function to append content consistently
def _append_to_content(
    current_content: Union[str, List[Any], None], new_item: Any
) -> Union[str, List[Any]]:
    """Appends a new item to the content, handling different initial content types."""
    if current_content is None and isinstance(new_item, str):
        return new_item
    elif current_content is None:
        return [new_item]
    elif isinstance(current_content, str):
        return [current_content, new_item]
    elif isinstance(current_content, list):
        current_content.append(new_item)
        return current_content
    else:
        # This case should ideally not be reached with proper type checking,
        # but it catches any unexpected types that might slip through.
        raise TypeError(f"Unexpected content type: {type(current_content)}")


def _parse_response_candidate(
    response_candidate: Candidate, streaming: bool = False
) -> AIMessage:
    content: Union[None, str, List[Union[str, dict]]] = None
    additional_kwargs: Dict[str, Any] = {}
    tool_calls = []
    invalid_tool_calls = []
    tool_call_chunks = []

    for part in response_candidate.content.parts:
        text: Optional[str] = None
        try:
            if hasattr(part, "text") and part.text is not None:
                text = part.text
                # Remove erroneous newline character if present
                if not streaming:
                    text = text.rstrip("\n")
        except AttributeError:
            pass

        if hasattr(part, "thought") and part.thought:
            thinking_message = {
                "type": "thinking",
                "thinking": part.text,
            }
            content = _append_to_content(content, thinking_message)
        elif text is not None and text:
            content = _append_to_content(content, text)

        if hasattr(part, "executable_code") and part.executable_code is not None:
            if part.executable_code.code and part.executable_code.language:
                code_message = {
                    "type": "executable_code",
                    "executable_code": part.executable_code.code,
                    "language": part.executable_code.language,
                }
                content = _append_to_content(content, code_message)

        if (
            hasattr(part, "code_execution_result")
            and part.code_execution_result is not None
        ):
            if part.code_execution_result.output:
                execution_result = {
                    "type": "code_execution_result",
                    "code_execution_result": part.code_execution_result.output,
                    "outcome": part.code_execution_result.outcome,
                }
                content = _append_to_content(content, execution_result)

        if part.inline_data.mime_type.startswith("audio/"):
            buffer = io.BytesIO()

            with wave.open(buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                # TODO: Read Sample Rate from MIME content type.
                wf.setframerate(24000)
                wf.writeframes(part.inline_data.data)

            additional_kwargs["audio"] = buffer.getvalue()

        if part.inline_data.mime_type.startswith("image/"):
            image_format = part.inline_data.mime_type[6:]
            image_message = {
                "type": "image_url",
                "image_url": {
                    "url": image_bytes_to_b64_string(
                        part.inline_data.data, image_format=image_format
                    )
                },
            }
            content = _append_to_content(content, image_message)

        if part.function_call:
            function_call = {"name": part.function_call.name}
            # dump to match other function calling llm for now
            function_call_args_dict = proto.Message.to_dict(part.function_call)["args"]
            function_call["arguments"] = json.dumps(
                {k: function_call_args_dict[k] for k in function_call_args_dict}
            )
            additional_kwargs["function_call"] = function_call

            if streaming:
                tool_call_chunks.append(
                    tool_call_chunk(
                        name=function_call.get("name"),
                        args=function_call.get("arguments"),
                        id=function_call.get("id", str(uuid.uuid4())),
                        index=function_call.get("index"),  # type: ignore
                    )
                )
            else:
                try:
                    tool_call_dict = parse_tool_calls(
                        [{"function": function_call}],
                        return_id=False,
                    )[0]
                except Exception as e:
                    invalid_tool_calls.append(
                        invalid_tool_call(
                            name=function_call.get("name"),
                            args=function_call.get("arguments"),
                            id=function_call.get("id", str(uuid.uuid4())),
                            error=str(e),
                        )
                    )
                else:
                    tool_calls.append(
                        tool_call(
                            name=tool_call_dict["name"],
                            args=tool_call_dict["args"],
                            id=tool_call_dict.get("id", str(uuid.uuid4())),
                        )
                    )
    if content is None:
        content = ""
    if any(isinstance(item, dict) and "executable_code" in item for item in content):
        warnings.warn(
            """
        ⚠️ Warning: Output may vary each run.  
        - 'executable_code': Always present.  
        - 'execution_result' & 'image_url': May be absent for some queries.  

        Validate before using in production.
"""
        )

    if streaming:
        return AIMessageChunk(
            content=cast(Union[str, List[Union[str, Dict[Any, Any]]]], content),
            additional_kwargs=additional_kwargs,
            tool_call_chunks=tool_call_chunks,
        )

    return AIMessage(
        content=cast(Union[str, List[Union[str, Dict[Any, Any]]]], content),
        additional_kwargs=additional_kwargs,
        tool_calls=tool_calls,
        invalid_tool_calls=invalid_tool_calls,
    )


def _response_to_result(
    response: GenerateContentResponse,
    stream: bool = False,
    prev_usage: Optional[UsageMetadata] = None,
) -> ChatResult:
    """Converts a PaLM API response into a LangChain ChatResult."""
    llm_output = {"prompt_feedback": proto.Message.to_dict(response.prompt_feedback)}

    # Get usage metadata
    try:
        input_tokens = response.usage_metadata.prompt_token_count
        thought_tokens = response.usage_metadata.thoughts_token_count
        output_tokens = response.usage_metadata.candidates_token_count + thought_tokens
        total_tokens = response.usage_metadata.total_token_count
        cache_read_tokens = response.usage_metadata.cached_content_token_count
        if input_tokens + output_tokens + cache_read_tokens + total_tokens > 0:
            if thought_tokens > 0:
                cumulative_usage = UsageMetadata(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    input_token_details={"cache_read": cache_read_tokens},
                    output_token_details={"reasoning": thought_tokens},
                )
            else:
                cumulative_usage = UsageMetadata(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    input_token_details={"cache_read": cache_read_tokens},
                )
            # previous usage metadata needs to be subtracted because gemini api returns
            # already-accumulated token counts with each chunk
            lc_usage = subtract_usage(cumulative_usage, prev_usage)
            if prev_usage and cumulative_usage["input_tokens"] < prev_usage.get(
                "input_tokens", 0
            ):
                # Gemini 1.5 and 2.0 return a lower cumulative count of prompt tokens
                # in the final chunk. We take this count to be ground truth because
                # it's consistent with the reported total tokens. So we need to
                # ensure this chunk compensates (the subtract_usage funcction floors
                # at zero).
                lc_usage["input_tokens"] = cumulative_usage[
                    "input_tokens"
                ] - prev_usage.get("input_tokens", 0)
        else:
            lc_usage = None
    except AttributeError:
        lc_usage = None

    generations: List[ChatGeneration] = []

    for candidate in response.candidates:
        generation_info = {}
        if candidate.finish_reason:
            generation_info["finish_reason"] = candidate.finish_reason.name
            # Add model_name in last chunk
            generation_info["model_name"] = response.model_version
        generation_info["safety_ratings"] = [
            proto.Message.to_dict(safety_rating, use_integers_for_enums=False)
            for safety_rating in candidate.safety_ratings
        ]
        try:
            if candidate.grounding_metadata:
                generation_info["grounding_metadata"] = proto.Message.to_dict(
                    candidate.grounding_metadata
                )
        except AttributeError:
            pass
        message = _parse_response_candidate(candidate, streaming=stream)
        message.usage_metadata = lc_usage
        if stream:
            generations.append(
                ChatGenerationChunk(
                    message=cast(AIMessageChunk, message),
                    generation_info=generation_info,
                )
            )
        else:
            generations.append(
                ChatGeneration(message=message, generation_info=generation_info)
            )
    if not response.candidates:
        # Likely a "prompt feedback" violation (e.g., toxic input)
        # Raising an error would be different than how OpenAI handles it,
        # so we'll just log a warning and continue with an empty message.
        logger.warning(
            "Gemini produced an empty response. Continuing with empty message\n"
            f"Feedback: {response.prompt_feedback}"
        )
        if stream:
            generations = [
                ChatGenerationChunk(
                    message=AIMessageChunk(content=""), generation_info={}
                )
            ]
        else:
            generations = [ChatGeneration(message=AIMessage(""), generation_info={})]
    return ChatResult(generations=generations, llm_output=llm_output)


def _is_event_loop_running() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


class ChatGoogleGenerativeAI(_BaseGoogleGenerativeAI, BaseChatModel):
    """`Google AI` chat models integration.

    Instantiation:
        To use, you must have either:

            1. The ``GOOGLE_API_KEY`` environment variable set with your API key, or
            2. Pass your API key using the ``google_api_key`` kwarg to the ChatGoogleGenerativeAI constructor.

        .. code-block:: python

            from langchain_google_genai import ChatGoogleGenerativeAI

            llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001")
            llm.invoke("Write me a ballad about LangChain")

    Invoke:
        .. code-block:: python

            messages = [
                ("system", "Translate the user sentence to French."),
                ("human", "I love programming."),
            ]
            llm.invoke(messages)

        .. code-block:: python

            AIMessage(
                content="J'adore programmer. \\n",
                response_metadata={'prompt_feedback': {'block_reason': 0, 'safety_ratings': []}, 'finish_reason': 'STOP', 'safety_ratings': [{'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_HATE_SPEECH', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_HARASSMENT', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'probability': 'NEGLIGIBLE', 'blocked': False}]},
                id='run-56cecc34-2e54-4b52-a974-337e47008ad2-0',
                usage_metadata={'input_tokens': 18, 'output_tokens': 5, 'total_tokens': 23}
            )

    Stream:
        .. code-block:: python

            for chunk in llm.stream(messages):
                print(chunk)

        .. code-block:: python

            AIMessageChunk(content='J', response_metadata={'finish_reason': 'STOP', 'safety_ratings': []}, id='run-e905f4f4-58cb-4a10-a960-448a2bb649e3', usage_metadata={'input_tokens': 18, 'output_tokens': 1, 'total_tokens': 19})
            AIMessageChunk(content="'adore programmer. \\n", response_metadata={'finish_reason': 'STOP', 'safety_ratings': [{'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_HATE_SPEECH', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_HARASSMENT', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'probability': 'NEGLIGIBLE', 'blocked': False}]}, id='run-e905f4f4-58cb-4a10-a960-448a2bb649e3', usage_metadata={'input_tokens': 18, 'output_tokens': 5, 'total_tokens': 23})

        .. code-block:: python

            stream = llm.stream(messages)
            full = next(stream)
            for chunk in stream:
                full += chunk
            full

        .. code-block:: python

            AIMessageChunk(
                content="J'adore programmer. \\n",
                response_metadata={'finish_reason': 'STOPSTOP', 'safety_ratings': [{'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_HATE_SPEECH', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_HARASSMENT', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'probability': 'NEGLIGIBLE', 'blocked': False}]},
                id='run-3ce13a42-cd30-4ad7-a684-f1f0b37cdeec',
                usage_metadata={'input_tokens': 36, 'output_tokens': 6, 'total_tokens': 42}
            )

    Async:
        .. code-block:: python

            await llm.ainvoke(messages)

            # stream:
            # async for chunk in (await llm.astream(messages))

            # batch:
            # await llm.abatch([messages])

    Context Caching:
        Context caching allows you to store and reuse content (e.g., PDFs, images) for faster processing.
        The ``cached_content`` parameter accepts a cache name created via the Google Generative AI API.
        Below are two examples: caching a single file directly and caching multiple files using ``Part``.

        Single File Example:
        This caches a single file and queries it.

        .. code-block:: python

            from google import genai
            from google.genai import types
            import time
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import HumanMessage

            client = genai.Client()

            # Upload file
            file = client.files.upload(file="./example_file")
            while file.state.name == 'PROCESSING':
                time.sleep(2)
                file = client.files.get(name=file.name)

            # Create cache
            model = 'models/gemini-1.5-flash-latest'
            cache = client.caches.create(
                model=model,
                config=types.CreateCachedContentConfig(
                    display_name='Cached Content',
                    system_instruction=(
                        'You are an expert content analyzer, and your job is to answer '
                        'the user\'s query based on the file you have access to.'
                    ),
                    contents=[file],
                    ttl="300s",
                )
            )

            # Query with LangChain
            llm = ChatGoogleGenerativeAI(
                model=model,
                cached_content=cache.name,
            )
            message = HumanMessage(content="Summarize the main points of the content.")
            llm.invoke([message])

        Multiple Files Example:
        This caches two files using `Part` and queries them together.

        .. code-block:: python

            from google import genai
            from google.genai.types import CreateCachedContentConfig, Content, Part
            import time
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_core.messages import HumanMessage

            client = genai.Client()

            # Upload files
            file_1 = client.files.upload(file="./file1")
            while file_1.state.name == 'PROCESSING':
                time.sleep(2)
                file_1 = client.files.get(name=file_1.name)

            file_2 = client.files.upload(file="./file2")
            while file_2.state.name == 'PROCESSING':
                time.sleep(2)
                file_2 = client.files.get(name=file_2.name)

            # Create cache with multiple files
            contents = [
                Content(
                    role="user",
                    parts=[
                        Part.from_uri(file_uri=file_1.uri, mime_type=file_1.mime_type),
                        Part.from_uri(file_uri=file_2.uri, mime_type=file_2.mime_type),
                    ],
                )
            ]
            model = "gemini-1.5-flash-latest"
            cache = client.caches.create(
                model=model,
                config=CreateCachedContentConfig(
                    display_name='Cached Contents',
                    system_instruction=(
                        'You are an expert content analyzer, and your job is to answer '
                        'the user\'s query based on the files you have access to.'
                    ),
                    contents=contents,
                    ttl="300s",
                )
            )

            # Query with LangChain
            llm = ChatGoogleGenerativeAI(
                model=model,
                cached_content=cache.name,
            )
            message = HumanMessage(content="Provide a summary of the key information across both files.")
            llm.invoke([message])

    Tool calling:
        .. code-block:: python

            from pydantic import BaseModel, Field


            class GetWeather(BaseModel):
                '''Get the current weather in a given location'''

                location: str = Field(
                    ..., description="The city and state, e.g. San Francisco, CA"
                )


            class GetPopulation(BaseModel):
                '''Get the current population in a given location'''

                location: str = Field(
                    ..., description="The city and state, e.g. San Francisco, CA"
                )


            llm_with_tools = llm.bind_tools([GetWeather, GetPopulation])
            ai_msg = llm_with_tools.invoke(
                "Which city is hotter today and which is bigger: LA or NY?"
            )
            ai_msg.tool_calls

        .. code-block:: python

            [{'name': 'GetWeather',
              'args': {'location': 'Los Angeles, CA'},
              'id': 'c186c99f-f137-4d52-947f-9e3deabba6f6'},
             {'name': 'GetWeather',
              'args': {'location': 'New York City, NY'},
              'id': 'cebd4a5d-e800-4fa5-babd-4aa286af4f31'},
             {'name': 'GetPopulation',
              'args': {'location': 'Los Angeles, CA'},
              'id': '4f92d897-f5e4-4d34-a3bc-93062c92591e'},
             {'name': 'GetPopulation',
              'args': {'location': 'New York City, NY'},
              'id': '634582de-5186-4e4b-968b-f192f0a93678'}]

    Use Search with Gemini 2:
        .. code-block:: python

            from google.ai.generativelanguage_v1beta.types import Tool as GenAITool
            llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")
            resp = llm.invoke(
                "When is the next total solar eclipse in US?",
                tools=[GenAITool(google_search={})],
            )

    Structured output:
        .. code-block:: python

            from typing import Optional

            from pydantic import BaseModel, Field


            class Joke(BaseModel):
                '''Joke to tell user.'''

                setup: str = Field(description="The setup of the joke")
                punchline: str = Field(description="The punchline to the joke")
                rating: Optional[int] = Field(description="How funny the joke is, from 1 to 10")


            structured_llm = llm.with_structured_output(Joke)
            structured_llm.invoke("Tell me a joke about cats")

        .. code-block:: python

            Joke(
                setup='Why are cats so good at video games?',
                punchline='They have nine lives on the internet',
                rating=None
            )

    Image input:
        .. code-block:: python

            import base64
            import httpx
            from langchain_core.messages import HumanMessage

            image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
            image_data = base64.b64encode(httpx.get(image_url).content).decode("utf-8")
            message = HumanMessage(
                content=[
                    {"type": "text", "text": "describe the weather in this image"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                    },
                ]
            )
            ai_msg = llm.invoke([message])
            ai_msg.content

        .. code-block:: python

            'The weather in this image appears to be sunny and pleasant. The sky is a bright blue with scattered white clouds, suggesting fair weather. The lush green grass and trees indicate a warm and possibly slightly breezy day. There are no signs of rain or storms.'

    Token usage:
        .. code-block:: python

            ai_msg = llm.invoke(messages)
            ai_msg.usage_metadata

        .. code-block:: python

            {'input_tokens': 18, 'output_tokens': 5, 'total_tokens': 23}


    Response metadata
        .. code-block:: python

            ai_msg = llm.invoke(messages)
            ai_msg.response_metadata

        .. code-block:: python

            {
                'prompt_feedback': {'block_reason': 0, 'safety_ratings': []},
                'finish_reason': 'STOP',
                'safety_ratings': [{'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_HATE_SPEECH', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_HARASSMENT', 'probability': 'NEGLIGIBLE', 'blocked': False}, {'category': 'HARM_CATEGORY_DANGEROUS_CONTENT', 'probability': 'NEGLIGIBLE', 'blocked': False}]
            }

    """  # noqa: E501

    client: Any = Field(default=None, exclude=True)  #: :meta private:
    async_client_running: Any = Field(default=None, exclude=True)  #: :meta private:
    default_metadata: Sequence[Tuple[str, str]] = Field(
        default_factory=list
    )  #: :meta private:

    convert_system_message_to_human: bool = False
    """Whether to merge any leading SystemMessage into the following HumanMessage.

    Gemini does not support system messages; any unsupported messages will
    raise an error."""

    response_mime_type: Optional[str] = None
    """Optional. Output response mimetype of the generated candidate text. Only
    supported in Gemini 1.5 and later models.
    
    Supported mimetype:
        * ``'text/plain'``: (default) Text output.
        * ``'application/json'``: JSON response in the candidates.
        * ``'text/x.enum'``: Enum in plain text.
    
    The model also needs to be prompted to output the appropriate response
    type, otherwise the behavior is undefined. This is a preview feature.
    """

    response_schema: Optional[Dict[str, Any]] = None
    """ Optional. Enforce an schema to the output.
        The format of the dictionary should follow Open API schema.
    """

    cached_content: Optional[str] = None
    """The name of the cached content used as context to serve the prediction. 

    Note: only used in explicit caching, where users can have control over caching 
    (e.g. what content to cache) and enjoy guaranteed cost savings. Format: 
    ``cachedContents/{cachedContent}``.
    """

    model_kwargs: dict[str, Any] = Field(default_factory=dict)
    """Holds any unexpected initialization parameters."""

    def __init__(self, **kwargs: Any) -> None:
        """Needed for arg validation."""
        # Get all valid field names, including aliases
        valid_fields = set()
        for field_name, field_info in self.__class__.model_fields.items():
            valid_fields.add(field_name)
            if hasattr(field_info, "alias") and field_info.alias is not None:
                valid_fields.add(field_info.alias)

        # Check for unrecognized arguments
        for arg in kwargs:
            if arg not in valid_fields:
                suggestions = get_close_matches(arg, valid_fields, n=1)
                suggestion = (
                    f" Did you mean: '{suggestions[0]}'?" if suggestions else ""
                )
                logger.warning(
                    f"Unexpected argument '{arg}' "
                    f"provided to ChatGoogleGenerativeAI.{suggestion}"
                )
        super().__init__(**kwargs)

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @property
    def lc_secrets(self) -> Dict[str, str]:
        return {"google_api_key": "GOOGLE_API_KEY"}

    @property
    def _llm_type(self) -> str:
        return "chat-google-generative-ai"

    @property
    def _supports_code_execution(self) -> bool:
        return (
            "gemini-1.5-pro" in self.model
            or "gemini-1.5-flash" in self.model
            or "gemini-2" in self.model
        )

    @classmethod
    def is_lc_serializable(self) -> bool:
        return True

    @model_validator(mode="before")
    @classmethod
    def build_extra(cls, values: dict[str, Any]) -> Any:
        """Build extra kwargs from additional params that were passed in."""
        all_required_field_names = get_pydantic_field_names(cls)
        values = _build_model_kwargs(values, all_required_field_names)
        return values

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        """Validates params and passes them to google-generativeai package."""
        if self.temperature is not None and not 0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be in the range [0.0, 2.0]")

        if self.top_p is not None and not 0 <= self.top_p <= 1:
            raise ValueError("top_p must be in the range [0.0, 1.0]")

        if self.top_k is not None and self.top_k <= 0:
            raise ValueError("top_k must be positive")

        if not any(self.model.startswith(prefix) for prefix in ("models/",)):
            self.model = f"models/{self.model}"

        additional_headers = self.additional_headers or {}
        self.default_metadata = tuple(additional_headers.items())
        client_info = get_client_info(f"ChatGoogleGenerativeAI:{self.model}")
        google_api_key = None
        if not self.credentials:
            if isinstance(self.google_api_key, SecretStr):
                google_api_key = self.google_api_key.get_secret_value()
            else:
                google_api_key = self.google_api_key
        transport: Optional[str] = self.transport
        self.client = genaix.build_generative_service(
            credentials=self.credentials,
            api_key=google_api_key,
            client_info=client_info,
            client_options=self.client_options,
            transport=transport,
        )
        self.async_client_running = None
        return self

    @property
    def async_client(self) -> v1betaGenerativeServiceAsyncClient:
        google_api_key = None
        if not self.credentials:
            if isinstance(self.google_api_key, SecretStr):
                google_api_key = self.google_api_key.get_secret_value()
            else:
                google_api_key = self.google_api_key
        # NOTE: genaix.build_generative_async_service requires
        # a running event loop, which causes an error
        # when initialized inside a ThreadPoolExecutor.
        # this check ensures that async client is only initialized
        # within an asyncio event loop to avoid the error
        if not self.async_client_running and _is_event_loop_running():
            # async clients don't support "rest" transport
            # https://github.com/googleapis/gapic-generator-python/issues/1962
            transport = self.transport
            if transport == "rest":
                transport = "grpc_asyncio"
            self.async_client_running = genaix.build_generative_async_service(
                credentials=self.credentials,
                api_key=google_api_key,
                client_info=get_client_info(f"ChatGoogleGenerativeAI:{self.model}"),
                client_options=self.client_options,
                transport=transport,
            )
        return self.async_client_running

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Get the identifying parameters."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_k": self.top_k,
            "n": self.n,
            "safety_settings": self.safety_settings,
            "response_modalities": self.response_modalities,
            "thinking_budget": self.thinking_budget,
            "include_thoughts": self.include_thoughts,
        }

    def invoke(
        self,
        input: LanguageModelInput,
        config: Optional[RunnableConfig] = None,
        *,
        code_execution: Optional[bool] = None,
        stop: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> BaseMessage:
        """
        Enable code execution. Supported on: gemini-1.5-pro, gemini-1.5-flash,
        gemini-2.0-flash, and gemini-2.0-pro. When enabled, the model can execute
        code to solve problems.
        """

        """Override invoke to add code_execution parameter."""

        if code_execution is not None:
            if not self._supports_code_execution:
                raise ValueError(
                    f"Code execution is only supported on Gemini 1.5 Pro, \
                    Gemini 1.5 Flash, "
                    f"Gemini 2.0 Flash, and Gemini 2.0 Pro models. \
                    Current model: {self.model}"
                )
            if "tools" not in kwargs:
                code_execution_tool = GoogleTool(code_execution=CodeExecution())
                kwargs["tools"] = [code_execution_tool]

            else:
                raise ValueError(
                    "Tools are already defined.code_execution tool can't be defined"
                )

        return super().invoke(input, config, stop=stop, **kwargs)

    def _get_ls_params(
        self, stop: Optional[List[str]] = None, **kwargs: Any
    ) -> LangSmithParams:
        """Get standard params for tracing."""
        params = self._get_invocation_params(stop=stop, **kwargs)
        models_prefix = "models/"
        ls_model_name = (
            self.model[len(models_prefix) :]
            if self.model and self.model.startswith(models_prefix)
            else self.model
        )
        ls_params = LangSmithParams(
            ls_provider="google_genai",
            ls_model_name=ls_model_name,
            ls_model_type="chat",
            ls_temperature=params.get("temperature", self.temperature),
        )
        if ls_max_tokens := params.get("max_output_tokens", self.max_output_tokens):
            ls_params["ls_max_tokens"] = ls_max_tokens
        if ls_stop := stop or params.get("stop", None):
            ls_params["ls_stop"] = ls_stop
        return ls_params

    def _prepare_params(
        self,
        stop: Optional[List[str]],
        generation_config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> GenerationConfig:
        gen_config = {
            k: v
            for k, v in {
                "candidate_count": self.n,
                "temperature": self.temperature,
                "stop_sequences": stop,
                "max_output_tokens": self.max_output_tokens,
                "top_k": self.top_k,
                "top_p": self.top_p,
                "response_modalities": self.response_modalities,
                "thinking_config": (
                    (
                        {"thinking_budget": self.thinking_budget}
                        if self.thinking_budget is not None
                        else {}
                    )
                    | (
                        {"include_thoughts": self.include_thoughts}
                        if self.include_thoughts is not None
                        else {}
                    )
                )
                if self.thinking_budget is not None or self.include_thoughts is not None
                else None,
            }.items()
            if v is not None
        }
        if generation_config:
            gen_config = {**gen_config, **generation_config}

        response_mime_type = kwargs.get("response_mime_type", self.response_mime_type)
        if response_mime_type is not None:
            gen_config["response_mime_type"] = response_mime_type

        response_schema = kwargs.get("response_schema", self.response_schema)
        if response_schema is not None:
            allowed_mime_types = ("application/json", "text/x.enum")
            if response_mime_type not in allowed_mime_types:
                error_message = (
                    "`response_schema` is only supported when "
                    f"`response_mime_type` is set to one of {allowed_mime_types}"
                )
                raise ValueError(error_message)

            gapic_response_schema = _dict_to_gapic_schema(response_schema)
            if gapic_response_schema is not None:
                gen_config["response_schema"] = gapic_response_schema
        return GenerationConfig(**gen_config)

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        *,
        tools: Optional[Sequence[Union[_ToolDict, GoogleTool]]] = None,
        functions: Optional[Sequence[_FunctionDeclarationType]] = None,
        safety_settings: Optional[SafetySettingDict] = None,
        tool_config: Optional[Union[Dict, _ToolConfigDict]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        cached_content: Optional[str] = None,
        tool_choice: Optional[Union[_ToolChoiceType, bool]] = None,
        **kwargs: Any,
    ) -> ChatResult:
        request = self._prepare_request(
            messages,
            stop=stop,
            tools=tools,
            functions=functions,
            safety_settings=safety_settings,
            tool_config=tool_config,
            generation_config=generation_config,
            cached_content=cached_content or self.cached_content,
            tool_choice=tool_choice,
            **kwargs,
        )
        response: GenerateContentResponse = _chat_with_retry(
            request=request,
            **kwargs,
            generation_method=self.client.generate_content,
            metadata=self.default_metadata,
        )
        return _response_to_result(response)

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        *,
        tools: Optional[Sequence[Union[_ToolDict, GoogleTool]]] = None,
        functions: Optional[Sequence[_FunctionDeclarationType]] = None,
        safety_settings: Optional[SafetySettingDict] = None,
        tool_config: Optional[Union[Dict, _ToolConfigDict]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        cached_content: Optional[str] = None,
        tool_choice: Optional[Union[_ToolChoiceType, bool]] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if not self.async_client:
            updated_kwargs = {
                **kwargs,
                **{
                    "tools": tools,
                    "functions": functions,
                    "safety_settings": safety_settings,
                    "tool_config": tool_config,
                    "generation_config": generation_config,
                },
            }
            return await super()._agenerate(
                messages, stop, run_manager, **updated_kwargs
            )

        request = self._prepare_request(
            messages,
            stop=stop,
            tools=tools,
            functions=functions,
            safety_settings=safety_settings,
            tool_config=tool_config,
            generation_config=generation_config,
            cached_content=cached_content or self.cached_content,
            tool_choice=tool_choice,
            **kwargs,
        )
        response: GenerateContentResponse = await _achat_with_retry(
            request=request,
            **kwargs,
            generation_method=self.async_client.generate_content,
            metadata=self.default_metadata,
        )
        return _response_to_result(response)

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        *,
        tools: Optional[Sequence[Union[_ToolDict, GoogleTool]]] = None,
        functions: Optional[Sequence[_FunctionDeclarationType]] = None,
        safety_settings: Optional[SafetySettingDict] = None,
        tool_config: Optional[Union[Dict, _ToolConfigDict]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        cached_content: Optional[str] = None,
        tool_choice: Optional[Union[_ToolChoiceType, bool]] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        request = self._prepare_request(
            messages,
            stop=stop,
            tools=tools,
            functions=functions,
            safety_settings=safety_settings,
            tool_config=tool_config,
            generation_config=generation_config,
            cached_content=cached_content or self.cached_content,
            tool_choice=tool_choice,
            **kwargs,
        )
        response: GenerateContentResponse = _chat_with_retry(
            request=request,
            generation_method=self.client.stream_generate_content,
            **kwargs,
            metadata=self.default_metadata,
        )

        prev_usage_metadata: UsageMetadata | None = None  # cumulative usage
        for chunk in response:
            _chat_result = _response_to_result(
                chunk, stream=True, prev_usage=prev_usage_metadata
            )
            gen = cast(ChatGenerationChunk, _chat_result.generations[0])
            message = cast(AIMessageChunk, gen.message)

            prev_usage_metadata = (
                message.usage_metadata
                if prev_usage_metadata is None
                else add_usage(prev_usage_metadata, message.usage_metadata)
            )

            if run_manager:
                run_manager.on_llm_new_token(gen.text)
            yield gen

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        *,
        tools: Optional[Sequence[Union[_ToolDict, GoogleTool]]] = None,
        functions: Optional[Sequence[_FunctionDeclarationType]] = None,
        safety_settings: Optional[SafetySettingDict] = None,
        tool_config: Optional[Union[Dict, _ToolConfigDict]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        cached_content: Optional[str] = None,
        tool_choice: Optional[Union[_ToolChoiceType, bool]] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        if not self.async_client:
            updated_kwargs = {
                **kwargs,
                **{
                    "tools": tools,
                    "functions": functions,
                    "safety_settings": safety_settings,
                    "tool_config": tool_config,
                    "generation_config": generation_config,
                },
            }
            async for value in super()._astream(
                messages, stop, run_manager, **updated_kwargs
            ):
                yield value
        else:
            request = self._prepare_request(
                messages,
                stop=stop,
                tools=tools,
                functions=functions,
                safety_settings=safety_settings,
                tool_config=tool_config,
                generation_config=generation_config,
                cached_content=cached_content or self.cached_content,
                tool_choice=tool_choice,
                **kwargs,
            )
            prev_usage_metadata: UsageMetadata | None = None  # cumulative usage
            async for chunk in await _achat_with_retry(
                request=request,
                generation_method=self.async_client.stream_generate_content,
                **kwargs,
                metadata=self.default_metadata,
            ):
                _chat_result = _response_to_result(
                    chunk, stream=True, prev_usage=prev_usage_metadata
                )
                gen = cast(ChatGenerationChunk, _chat_result.generations[0])
                message = cast(AIMessageChunk, gen.message)

                prev_usage_metadata = (
                    message.usage_metadata
                    if prev_usage_metadata is None
                    else add_usage(prev_usage_metadata, message.usage_metadata)
                )

                if run_manager:
                    await run_manager.on_llm_new_token(gen.text)
                yield gen

    def _prepare_request(
        self,
        messages: List[BaseMessage],
        *,
        stop: Optional[List[str]] = None,
        tools: Optional[Sequence[Union[_ToolDict, GoogleTool]]] = None,
        functions: Optional[Sequence[_FunctionDeclarationType]] = None,
        safety_settings: Optional[SafetySettingDict] = None,
        tool_config: Optional[Union[Dict, _ToolConfigDict]] = None,
        tool_choice: Optional[Union[_ToolChoiceType, bool]] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        cached_content: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[GenerateContentRequest, Dict[str, Any]]:
        if tool_choice and tool_config:
            raise ValueError(
                "Must specify at most one of tool_choice and tool_config, received "
                f"both:\n\n{tool_choice=}\n\n{tool_config=}"
            )

        formatted_tools = None
        code_execution_tool = GoogleTool(code_execution=CodeExecution())
        if tools == [code_execution_tool]:
            formatted_tools = tools
        elif tools:
            formatted_tools = [convert_to_genai_function_declarations(tools)]
        elif functions:
            formatted_tools = [convert_to_genai_function_declarations(functions)]

        filtered_messages = []
        for message in messages:
            if isinstance(message, HumanMessage) and not message.content:
                warnings.warn(
                    "HumanMessage with empty content was removed to prevent API error"
                )
            else:
                filtered_messages.append(message)
        messages = filtered_messages

        system_instruction, history = _parse_chat_history(
            messages,
            convert_system_message_to_human=self.convert_system_message_to_human,
        )
        if tool_choice:
            if not formatted_tools:
                msg = (
                    f"Received {tool_choice=} but no {tools=}. 'tool_choice' can only "
                    f"be specified if 'tools' is specified."
                )
                raise ValueError(msg)
            all_names: List[str] = []
            for t in formatted_tools:
                if hasattr(t, "function_declarations"):
                    t_with_declarations = cast(Any, t)
                    all_names.extend(
                        f.name for f in t_with_declarations.function_declarations
                    )
                elif isinstance(t, GoogleTool) and hasattr(t, "code_execution"):
                    continue
                else:
                    raise TypeError(
                        f"Tool {t} doesn't have function_declarations attribute"
                    )

            tool_config = _tool_choice_to_tool_config(tool_choice, all_names)

        formatted_tool_config = None
        if tool_config:
            formatted_tool_config = ToolConfig(
                function_calling_config=tool_config["function_calling_config"]
            )
        formatted_safety_settings = []
        if safety_settings:
            formatted_safety_settings = [
                SafetySetting(category=c, threshold=t)
                for c, t in safety_settings.items()
            ]
        request = GenerateContentRequest(
            model=self.model,
            contents=history,
            tools=formatted_tools,
            tool_config=formatted_tool_config,
            safety_settings=formatted_safety_settings,
            generation_config=self._prepare_params(
                stop,
                generation_config=generation_config,
                **kwargs,
            ),
            cached_content=cached_content,
        )
        if system_instruction:
            request.system_instruction = system_instruction

        return request

    def get_num_tokens(self, text: str) -> int:
        """Get the number of tokens present in the text.

        Useful for checking if an input will fit in a model's context window.

        Args:
            text: The string input to tokenize.

        Returns:
            The integer number of tokens in the text.
        """
        result = self.client.count_tokens(
            model=self.model, contents=[Content(parts=[Part(text=text)])]
        )
        return result.total_tokens

    def with_structured_output(
        self,
        schema: Union[Dict, Type[BaseModel]],
        method: Optional[Literal["function_calling", "json_mode"]] = "function_calling",
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, Union[Dict, BaseModel]]:
        _ = kwargs.pop("strict", None)
        if kwargs:
            raise ValueError(f"Received unsupported arguments {kwargs}")

        parser: OutputParserLike

        if method == "json_mode":
            if isinstance(schema, type) and is_basemodel_subclass(schema):
                if issubclass(schema, BaseModelV1):
                    schema_json = schema.schema()
                else:
                    schema_json = schema.model_json_schema()
                parser = PydanticOutputParser(pydantic_object=schema)
            else:
                if is_typeddict(schema):
                    schema_json = convert_to_json_schema(schema)
                elif isinstance(schema, dict):
                    schema_json = schema
                else:
                    raise ValueError(f"Unsupported schema type {type(schema)}")
                parser = JsonOutputParser()

            # Resolve refs in schema because they are not supported
            # by the Gemini API.
            schema_json = replace_defs_in_schema(schema_json)

            llm = self.bind(
                response_mime_type="application/json",
                response_schema=schema_json,
                ls_structured_output_format={
                    "kwargs": {"method": method},
                    "schema": schema_json,
                },
            )
        else:
            tool_name = _get_tool_name(schema)  # type: ignore[arg-type]
            if isinstance(schema, type) and is_basemodel_subclass_safe(schema):
                parser = PydanticToolsParser(tools=[schema], first_tool_only=True)
            else:
                parser = JsonOutputKeyToolsParser(
                    key_name=tool_name, first_tool_only=True
                )
            tool_choice = tool_name if self._supports_tool_choice else None
            try:
                llm = self.bind_tools(
                    [schema],
                    tool_choice=tool_choice,
                    ls_structured_output_format={
                        "kwargs": {"method": "function_calling"},
                        "schema": convert_to_openai_tool(schema),
                    },
                )
            except Exception:
                llm = self.bind_tools([schema], tool_choice=tool_choice)
        if include_raw:
            parser_with_fallback = RunnablePassthrough.assign(
                parsed=itemgetter("raw") | parser, parsing_error=lambda _: None
            ).with_fallbacks(
                [RunnablePassthrough.assign(parsed=lambda _: None)],
                exception_key="parsing_error",
            )
            return {"raw": llm} | parser_with_fallback
        else:
            return llm | parser

    def bind_tools(
        self,
        tools: Sequence[
            dict[str, Any] | type | Callable[..., Any] | BaseTool | GoogleTool
        ],
        tool_config: Optional[Union[Dict, _ToolConfigDict]] = None,
        *,
        tool_choice: Optional[Union[_ToolChoiceType, bool]] = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, BaseMessage]:
        """Bind tool-like objects to this chat model.

        Assumes model is compatible with google-generativeAI tool-calling API.

        Args:
            tools: A list of tool definitions to bind to this chat model.
                Can be a pydantic model, callable, or BaseTool. Pydantic
                models, callables, and BaseTools will be automatically converted to
                their schema dictionary representation.
            **kwargs: Any additional parameters to pass to the
                :class:`~langchain.runnable.Runnable` constructor.
        """
        if tool_choice and tool_config:
            raise ValueError(
                "Must specify at most one of tool_choice and tool_config, received "
                f"both:\n\n{tool_choice=}\n\n{tool_config=}"
            )
        try:
            formatted_tools: list = [convert_to_openai_tool(tool) for tool in tools]  # type: ignore[arg-type]
        except Exception:
            formatted_tools = [
                tool_to_dict(convert_to_genai_function_declarations(tools))
            ]
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        elif tool_config:
            kwargs["tool_config"] = tool_config
        else:
            pass
        return self.bind(tools=formatted_tools, **kwargs)

    @property
    def _supports_tool_choice(self) -> bool:
        return (
            "gemini-1.5-pro" in self.model
            or "gemini-1.5-flash" in self.model
            or "gemini-2" in self.model
        )


def _get_tool_name(
    tool: Union[_ToolDict, GoogleTool, Dict],
) -> str:
    try:
        genai_tool = tool_to_dict(convert_to_genai_function_declarations([tool]))
        return [f["name"] for f in genai_tool["function_declarations"]][0]  # type: ignore[index]
    except ValueError as e:  # other TypedDict
        if is_typeddict(tool):
            return convert_to_openai_tool(cast(Dict, tool))["function"]["name"]
        else:
            raise e
