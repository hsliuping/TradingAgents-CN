import copy
import json
import logging
import time
from opentelemetry.instrumentation.openai.shared.config import Config
from wrapt import ObjectProxy


from opentelemetry import context as context_api
from opentelemetry.metrics import Counter, Histogram
from opentelemetry.semconv_ai import (
    SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY,
    SpanAttributes,
    LLMRequestTypeValues,
)

from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY
from opentelemetry.instrumentation.openai.utils import (
    _with_chat_telemetry_wrapper,
    dont_throw,
    run_async,
)
from opentelemetry.instrumentation.openai.shared import (
    metric_shared_attributes,
    _set_client_attributes,
    _set_request_attributes,
    _set_span_attribute,
    _set_functions_attributes,
    _token_type,
    set_tools_attributes,
    _set_response_attributes,
    is_streaming_response,
    should_send_prompts,
    model_as_dict,
    _get_openai_base_url,
    OPENAI_LLM_USAGE_TOKEN_TYPES,
    should_record_stream_token_usage,
    get_token_count_from_string,
    _set_span_stream_usage,
    propagate_trace_context,
)
from opentelemetry.trace import SpanKind, Tracer
from opentelemetry.trace.status import Status, StatusCode

from opentelemetry.instrumentation.openai.utils import is_openai_v1

SPAN_NAME = "openai.chat"
PROMPT_FILTER_KEY = "prompt_filter_results"
CONTENT_FILTER_KEY = "content_filter_results"

LLM_REQUEST_TYPE = LLMRequestTypeValues.CHAT

logger = logging.getLogger(__name__)


@_with_chat_telemetry_wrapper
def chat_wrapper(
    tracer: Tracer,
    token_counter: Counter,
    choice_counter: Counter,
    duration_histogram: Histogram,
    exception_counter: Counter,
    streaming_time_to_first_token: Histogram,
    streaming_time_to_generate: Histogram,
    wrapped,
    instance,
    args,
    kwargs,
):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY) or context_api.get_value(
        SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY
    ):
        return wrapped(*args, **kwargs)
    # span needs to be opened and closed manually because the response is a generator

    span = tracer.start_span(
        SPAN_NAME,
        kind=SpanKind.CLIENT,
        attributes={SpanAttributes.LLM_REQUEST_TYPE: LLM_REQUEST_TYPE.value},
    )

    run_async(_handle_request(span, kwargs, instance))

    try:
        start_time = time.time()
        response = wrapped(*args, **kwargs)
        end_time = time.time()
    except Exception as e:  # pylint: disable=broad-except
        end_time = time.time()
        duration = end_time - start_time if "start_time" in locals() else 0

        attributes = {
            "error.type": e.__class__.__name__,
        }

        if duration > 0 and duration_histogram:
            duration_histogram.record(duration, attributes=attributes)
        if exception_counter:
            exception_counter.add(1, attributes=attributes)

        span.set_status(Status(StatusCode.ERROR, str(e)))
        span.end()

        raise e

    if is_streaming_response(response):
        # span will be closed after the generator is done
        if is_openai_v1():
            return ChatStream(
                span,
                response,
                instance,
                token_counter,
                choice_counter,
                duration_histogram,
                streaming_time_to_first_token,
                streaming_time_to_generate,
                start_time,
                kwargs,
            )
        else:
            return _build_from_streaming_response(
                span,
                response,
                instance,
                token_counter,
                choice_counter,
                duration_histogram,
                streaming_time_to_first_token,
                streaming_time_to_generate,
                start_time,
                kwargs,
            )

    duration = end_time - start_time

    _handle_response(
        response,
        span,
        instance,
        token_counter,
        choice_counter,
        duration_histogram,
        duration,
    )
    span.end()

    return response


@_with_chat_telemetry_wrapper
async def achat_wrapper(
    tracer: Tracer,
    token_counter: Counter,
    choice_counter: Counter,
    duration_histogram: Histogram,
    exception_counter: Counter,
    streaming_time_to_first_token: Histogram,
    streaming_time_to_generate: Histogram,
    wrapped,
    instance,
    args,
    kwargs,
):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY) or context_api.get_value(
        SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY
    ):
        return await wrapped(*args, **kwargs)

    span = tracer.start_span(
        SPAN_NAME,
        kind=SpanKind.CLIENT,
        attributes={SpanAttributes.LLM_REQUEST_TYPE: LLM_REQUEST_TYPE.value},
    )
    await _handle_request(span, kwargs, instance)

    try:
        start_time = time.time()
        response = await wrapped(*args, **kwargs)
        end_time = time.time()
    except Exception as e:  # pylint: disable=broad-except
        end_time = time.time()
        duration = end_time - start_time if "start_time" in locals() else 0

        common_attributes = Config.get_common_metrics_attributes()
        attributes = {
            **common_attributes,
            "error.type": e.__class__.__name__,
        }

        if duration > 0 and duration_histogram:
            duration_histogram.record(duration, attributes=attributes)
        if exception_counter:
            exception_counter.add(1, attributes=attributes)

        span.set_status(Status(StatusCode.ERROR, str(e)))
        span.end()

        raise e

    if is_streaming_response(response):
        # span will be closed after the generator is done
        if is_openai_v1():
            return ChatStream(
                span,
                response,
                instance,
                token_counter,
                choice_counter,
                duration_histogram,
                streaming_time_to_first_token,
                streaming_time_to_generate,
                start_time,
                kwargs,
            )
        else:
            return _abuild_from_streaming_response(
                span,
                response,
                instance,
                token_counter,
                choice_counter,
                duration_histogram,
                streaming_time_to_first_token,
                streaming_time_to_generate,
                start_time,
                kwargs,
            )

    duration = end_time - start_time

    _handle_response(
        response,
        span,
        instance,
        token_counter,
        choice_counter,
        duration_histogram,
        duration,
    )
    span.end()

    return response


@dont_throw
async def _handle_request(span, kwargs, instance):
    _set_request_attributes(span, kwargs)
    _set_client_attributes(span, instance)
    if should_send_prompts():
        await _set_prompts(span, kwargs.get("messages"))
        if kwargs.get("functions"):
            _set_functions_attributes(span, kwargs.get("functions"))
        elif kwargs.get("tools"):
            set_tools_attributes(span, kwargs.get("tools"))
    if Config.enable_trace_context_propagation:
        propagate_trace_context(span, kwargs)


@dont_throw
def _handle_response(
    response,
    span,
    instance=None,
    token_counter=None,
    choice_counter=None,
    duration_histogram=None,
    duration=None,
):
    if is_openai_v1():
        response_dict = model_as_dict(response)
    else:
        response_dict = response

    # metrics record
    _set_chat_metrics(
        instance,
        token_counter,
        choice_counter,
        duration_histogram,
        response_dict,
        duration,
    )

    # span attributes
    _set_response_attributes(span, response_dict)

    if should_send_prompts():
        _set_completions(span, response_dict.get("choices"))

    return response


def _set_chat_metrics(
    instance, token_counter, choice_counter, duration_histogram, response_dict, duration
):
    shared_attributes = metric_shared_attributes(
        response_model=response_dict.get("model") or None,
        operation="chat",
        server_address=_get_openai_base_url(instance),
        is_streaming=False,
    )

    # token metrics
    usage = response_dict.get("usage")  # type: dict
    if usage and token_counter:
        _set_token_counter_metrics(token_counter, usage, shared_attributes)

    # choices metrics
    choices = response_dict.get("choices")
    if choices and choice_counter:
        _set_choice_counter_metrics(choice_counter, choices, shared_attributes)

    # duration metrics
    if duration and isinstance(duration, (float, int)) and duration_histogram:
        duration_histogram.record(duration, attributes=shared_attributes)


def _set_choice_counter_metrics(choice_counter, choices, shared_attributes):
    choice_counter.add(len(choices), attributes=shared_attributes)
    for choice in choices:
        attributes_with_reason = {**shared_attributes}
        if choice.get("finish_reason"):
            attributes_with_reason[SpanAttributes.LLM_RESPONSE_FINISH_REASON] = (
                choice.get("finish_reason")
            )
        choice_counter.add(1, attributes=attributes_with_reason)


def _set_token_counter_metrics(token_counter, usage, shared_attributes):
    for name, val in usage.items():
        if name in OPENAI_LLM_USAGE_TOKEN_TYPES:
            attributes_with_token_type = {
                **shared_attributes,
                SpanAttributes.LLM_TOKEN_TYPE: _token_type(name),
            }
            token_counter.record(val, attributes=attributes_with_token_type)


def _is_base64_image(item):
    if not isinstance(item, dict):
        return False

    if not isinstance(item.get("image_url"), dict):
        return False

    if "data:image/" not in item.get("image_url", {}).get("url", ""):
        return False

    return True


async def _process_image_item(item, trace_id, span_id, message_index, content_index):
    if not Config.upload_base64_image:
        return item

    image_format = item["image_url"]["url"].split(";")[0].split("/")[1]
    image_name = f"message_{message_index}_content_{content_index}.{image_format}"
    base64_string = item["image_url"]["url"].split(",")[1]
    url = await Config.upload_base64_image(trace_id, span_id, image_name, base64_string)

    return {"type": "image_url", "image_url": {"url": url}}


@dont_throw
async def _set_prompts(span, messages):
    if not span.is_recording() or messages is None:
        return

    for i, msg in enumerate(messages):
        prefix = f"{SpanAttributes.LLM_PROMPTS}.{i}"
        msg = msg if isinstance(msg, dict) else model_as_dict(msg)

        _set_span_attribute(span, f"{prefix}.role", msg.get("role"))
        if msg.get("content"):
            content = copy.deepcopy(msg.get("content"))
            if isinstance(content, list):
                content = [
                    (
                        await _process_image_item(
                            item, span.context.trace_id, span.context.span_id, i, j
                        )
                        if _is_base64_image(item)
                        else item
                    )
                    for j, item in enumerate(content)
                ]

                content = json.dumps(content)
            _set_span_attribute(span, f"{prefix}.content", content)
        if msg.get("tool_call_id"):
            _set_span_attribute(span, f"{prefix}.tool_call_id", msg.get("tool_call_id"))
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            for i, tool_call in enumerate(tool_calls):
                if is_openai_v1():
                    tool_call = model_as_dict(tool_call)

                function = tool_call.get("function")
                _set_span_attribute(
                    span,
                    f"{prefix}.tool_calls.{i}.id",
                    tool_call.get("id"),
                )
                _set_span_attribute(
                    span,
                    f"{prefix}.tool_calls.{i}.name",
                    function.get("name"),
                )
                _set_span_attribute(
                    span,
                    f"{prefix}.tool_calls.{i}.arguments",
                    function.get("arguments"),
                )


def _set_completions(span, choices):
    if choices is None:
        return

    for choice in choices:
        index = choice.get("index")
        prefix = f"{SpanAttributes.LLM_COMPLETIONS}.{index}"
        _set_span_attribute(
            span, f"{prefix}.finish_reason", choice.get("finish_reason")
        )

        if choice.get("content_filter_results"):
            _set_span_attribute(
                span,
                f"{prefix}.{CONTENT_FILTER_KEY}",
                json.dumps(choice.get("content_filter_results")),
            )

        if choice.get("finish_reason") == "content_filter":
            _set_span_attribute(span, f"{prefix}.role", "assistant")
            _set_span_attribute(span, f"{prefix}.content", "FILTERED")

            return

        message = choice.get("message")
        if not message:
            return

        _set_span_attribute(span, f"{prefix}.role", message.get("role"))

        if message.get("refusal"):
            _set_span_attribute(span, f"{prefix}.refusal", message.get("refusal"))
        else:
            _set_span_attribute(span, f"{prefix}.content", message.get("content"))

        function_call = message.get("function_call")
        if function_call:
            _set_span_attribute(
                span, f"{prefix}.tool_calls.0.name", function_call.get("name")
            )
            _set_span_attribute(
                span,
                f"{prefix}.tool_calls.0.arguments",
                function_call.get("arguments"),
            )

        tool_calls = message.get("tool_calls")
        if tool_calls:
            for i, tool_call in enumerate(tool_calls):
                function = tool_call.get("function")
                _set_span_attribute(
                    span,
                    f"{prefix}.tool_calls.{i}.id",
                    tool_call.get("id"),
                )
                _set_span_attribute(
                    span,
                    f"{prefix}.tool_calls.{i}.name",
                    function.get("name"),
                )
                _set_span_attribute(
                    span,
                    f"{prefix}.tool_calls.{i}.arguments",
                    function.get("arguments"),
                )


@dont_throw
def _set_streaming_token_metrics(
    request_kwargs, complete_response, span, token_counter, shared_attributes
):
    # use tiktoken calculate token usage
    if not should_record_stream_token_usage():
        return

    # kwargs={'model': 'gpt-3.5', 'messages': [{'role': 'user', 'content': '...'}], 'stream': True}
    prompt_usage = -1
    completion_usage = -1

    # prompt_usage
    if request_kwargs and request_kwargs.get("messages"):
        prompt_content = ""
        # setting the default model_name as gpt-4. As this uses the embedding "cl100k_base" that
        # is used by most of the other model.
        model_name = (
            complete_response.get("model") or request_kwargs.get("model") or "gpt-4"
        )
        for msg in request_kwargs.get("messages"):
            if msg.get("content"):
                prompt_content += msg.get("content")
        if model_name:
            prompt_usage = get_token_count_from_string(prompt_content, model_name)

    # completion_usage
    if complete_response.get("choices"):
        completion_content = ""
        # setting the default model_name as gpt-4. As this uses the embedding "cl100k_base" that
        # is used by most of the other model.
        model_name = complete_response.get("model") or "gpt-4"

        for choice in complete_response.get("choices"):
            if choice.get("message") and choice.get("message").get("content"):
                completion_content += choice["message"]["content"]

        if model_name:
            completion_usage = get_token_count_from_string(
                completion_content, model_name
            )

    # span record
    _set_span_stream_usage(span, prompt_usage, completion_usage)

    # metrics record
    if token_counter:
        if type(prompt_usage) is int and prompt_usage >= 0:
            attributes_with_token_type = {
                **shared_attributes,
                SpanAttributes.LLM_TOKEN_TYPE: "input",
            }
            token_counter.record(prompt_usage, attributes=attributes_with_token_type)

        if type(completion_usage) is int and completion_usage >= 0:
            attributes_with_token_type = {
                **shared_attributes,
                SpanAttributes.LLM_TOKEN_TYPE: "output",
            }
            token_counter.record(
                completion_usage, attributes=attributes_with_token_type
            )


class ChatStream(ObjectProxy):
    _span = None
    _instance = None
    _token_counter = None
    _choice_counter = None
    _duration_histogram = None
    _streaming_time_to_first_token = None
    _streaming_time_to_generate = None
    _start_time = None
    _request_kwargs = None

    def __init__(
        self,
        span,
        response,
        instance=None,
        token_counter=None,
        choice_counter=None,
        duration_histogram=None,
        streaming_time_to_first_token=None,
        streaming_time_to_generate=None,
        start_time=None,
        request_kwargs=None,
    ):
        super().__init__(response)

        self._span = span
        self._instance = instance
        self._token_counter = token_counter
        self._choice_counter = choice_counter
        self._duration_histogram = duration_histogram
        self._streaming_time_to_first_token = streaming_time_to_first_token
        self._streaming_time_to_generate = streaming_time_to_generate
        self._start_time = start_time
        self._request_kwargs = request_kwargs

        self._first_token = True
        # will be updated when first token is received
        self._time_of_first_token = self._start_time
        self._complete_response = {"choices": [], "model": ""}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__wrapped__.__exit__(exc_type, exc_val, exc_tb)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.__wrapped__.__aexit__(exc_type, exc_val, exc_tb)

    def __iter__(self):
        return self

    def __aiter__(self):
        return self

    def __next__(self):
        try:
            chunk = self.__wrapped__.__next__()
        except Exception as e:
            if isinstance(e, StopIteration):
                self._close_span()
            raise e
        else:
            self._process_item(chunk)
            return chunk

    async def __anext__(self):
        try:
            chunk = await self.__wrapped__.__anext__()
        except Exception as e:
            if isinstance(e, StopAsyncIteration):
                self._close_span()
            raise e
        else:
            self._process_item(chunk)
            return chunk

    def _process_item(self, item):
        self._span.add_event(name=f"{SpanAttributes.LLM_CONTENT_COMPLETION_CHUNK}")

        if self._first_token and self._streaming_time_to_first_token:
            self._time_of_first_token = time.time()
            self._streaming_time_to_first_token.record(
                self._time_of_first_token - self._start_time,
                attributes=self._shared_attributes(),
            )
            self._first_token = False

        _accumulate_stream_items(item, self._complete_response)

    def _shared_attributes(self):
        return metric_shared_attributes(
            response_model=self._complete_response.get("model")
            or self._request_kwargs.get("model")
            or None,
            operation="chat",
            server_address=_get_openai_base_url(self._instance),
            is_streaming=True,
        )

    @dont_throw
    def _close_span(self):
        _set_streaming_token_metrics(
            self._request_kwargs,
            self._complete_response,
            self._span,
            self._token_counter,
            self._shared_attributes(),
        )

        # choice metrics
        if self._choice_counter and self._complete_response.get("choices"):
            _set_choice_counter_metrics(
                self._choice_counter,
                self._complete_response.get("choices"),
                self._shared_attributes(),
            )

        # duration metrics
        if self._start_time and isinstance(self._start_time, (float, int)):
            duration = time.time() - self._start_time
        else:
            duration = None
        if duration and isinstance(duration, (float, int)) and self._duration_histogram:
            self._duration_histogram.record(
                duration, attributes=self._shared_attributes()
            )
        if self._streaming_time_to_generate and self._time_of_first_token:
            self._streaming_time_to_generate.record(
                time.time() - self._time_of_first_token,
                attributes=self._shared_attributes(),
            )

        _set_response_attributes(self._span, self._complete_response)

        if should_send_prompts():
            _set_completions(self._span, self._complete_response.get("choices"))

        self._span.set_status(Status(StatusCode.OK))
        self._span.end()


# Backward compatibility with OpenAI v0


@dont_throw
def _build_from_streaming_response(
    span,
    response,
    instance=None,
    token_counter=None,
    choice_counter=None,
    duration_histogram=None,
    streaming_time_to_first_token=None,
    streaming_time_to_generate=None,
    start_time=None,
    request_kwargs=None,
):
    complete_response = {"choices": [], "model": "", "id": ""}

    first_token = True
    time_of_first_token = start_time  # will be updated when first token is received

    for item in response:
        span.add_event(name=f"{SpanAttributes.LLM_CONTENT_COMPLETION_CHUNK}")

        item_to_yield = item

        if first_token and streaming_time_to_first_token:
            time_of_first_token = time.time()
            streaming_time_to_first_token.record(time_of_first_token - start_time)
            first_token = False

        _accumulate_stream_items(item, complete_response)

        yield item_to_yield

    shared_attributes = {
        SpanAttributes.LLM_RESPONSE_MODEL: complete_response.get("model") or None,
        "server.address": _get_openai_base_url(instance),
        "stream": True,
    }

    _set_streaming_token_metrics(
        request_kwargs, complete_response, span, token_counter, shared_attributes
    )

    # choice metrics
    if choice_counter and complete_response.get("choices"):
        _set_choice_counter_metrics(
            choice_counter, complete_response.get("choices"), shared_attributes
        )

    # duration metrics
    if start_time and isinstance(start_time, (float, int)):
        duration = time.time() - start_time
    else:
        duration = None
    if duration and isinstance(duration, (float, int)) and duration_histogram:
        duration_histogram.record(duration, attributes=shared_attributes)
    if streaming_time_to_generate and time_of_first_token:
        streaming_time_to_generate.record(time.time() - time_of_first_token)

    _set_response_attributes(span, complete_response)

    if should_send_prompts():
        _set_completions(span, complete_response.get("choices"))

    span.set_status(Status(StatusCode.OK))
    span.end()


@dont_throw
async def _abuild_from_streaming_response(
    span,
    response,
    instance=None,
    token_counter=None,
    choice_counter=None,
    duration_histogram=None,
    streaming_time_to_first_token=None,
    streaming_time_to_generate=None,
    start_time=None,
    request_kwargs=None,
):
    complete_response = {"choices": [], "model": "", "id": ""}

    first_token = True
    time_of_first_token = start_time  # will be updated when first token is received

    async for item in response:
        span.add_event(name=f"{SpanAttributes.LLM_CONTENT_COMPLETION_CHUNK}")

        item_to_yield = item

        if first_token and streaming_time_to_first_token:
            time_of_first_token = time.time()
            streaming_time_to_first_token.record(time_of_first_token - start_time)
            first_token = False

        _accumulate_stream_items(item, complete_response)

        yield item_to_yield

    shared_attributes = {
        SpanAttributes.LLM_RESPONSE_MODEL: complete_response.get("model") or None,
        "server.address": _get_openai_base_url(instance),
        "stream": True,
    }

    _set_streaming_token_metrics(
        request_kwargs, complete_response, span, token_counter, shared_attributes
    )

    # choice metrics
    if choice_counter and complete_response.get("choices"):
        _set_choice_counter_metrics(
            choice_counter, complete_response.get("choices"), shared_attributes
        )

    # duration metrics
    if start_time and isinstance(start_time, (float, int)):
        duration = time.time() - start_time
    else:
        duration = None
    if duration and isinstance(duration, (float, int)) and duration_histogram:
        duration_histogram.record(duration, attributes=shared_attributes)
    if streaming_time_to_generate and time_of_first_token:
        streaming_time_to_generate.record(time.time() - time_of_first_token)

    _set_response_attributes(span, complete_response)

    if should_send_prompts():
        _set_completions(span, complete_response.get("choices"))

    span.set_status(Status(StatusCode.OK))
    span.end()


def _accumulate_stream_items(item, complete_response):
    if is_openai_v1():
        item = model_as_dict(item)

    complete_response["model"] = item.get("model")
    complete_response["id"] = item.get("id")

    # prompt filter results
    if item.get("prompt_filter_results"):
        complete_response["prompt_filter_results"] = item.get("prompt_filter_results")

    for choice in item.get("choices"):
        index = choice.get("index")
        if len(complete_response.get("choices")) <= index:
            complete_response["choices"].append(
                {"index": index, "message": {"content": "", "role": ""}}
            )
        complete_choice = complete_response.get("choices")[index]
        if choice.get("finish_reason"):
            complete_choice["finish_reason"] = choice.get("finish_reason")
        if choice.get("content_filter_results"):
            complete_choice["content_filter_results"] = choice.get(
                "content_filter_results"
            )

        delta = choice.get("delta")

        if delta and delta.get("content"):
            complete_choice["message"]["content"] += delta.get("content")

        if delta and delta.get("role"):
            complete_choice["message"]["role"] = delta.get("role")
        if delta and delta.get("tool_calls"):
            tool_calls = delta.get("tool_calls")
            if not isinstance(tool_calls, list) or len(tool_calls) == 0:
                continue

            if not complete_choice["message"].get("tool_calls"):
                complete_choice["message"]["tool_calls"] = []

            for tool_call in tool_calls:
                i = int(tool_call["index"])
                if len(complete_choice["message"]["tool_calls"]) <= i:
                    complete_choice["message"]["tool_calls"].append(
                        {"id": "", "function": {"name": "", "arguments": ""}}
                    )

                span_tool_call = complete_choice["message"]["tool_calls"][i]
                span_function = span_tool_call["function"]
                tool_call_function = tool_call.get("function")

                if tool_call.get("id"):
                    span_tool_call["id"] = tool_call.get("id")
                if tool_call_function and tool_call_function.get("name"):
                    span_function["name"] = tool_call_function.get("name")
                if tool_call_function and tool_call_function.get("arguments"):
                    span_function["arguments"] += tool_call_function.get("arguments")
