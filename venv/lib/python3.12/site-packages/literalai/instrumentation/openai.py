import logging
import time
from typing import TYPE_CHECKING, Dict, Union

from literalai.instrumentation import OPENAI_PROVIDER
from literalai.requirements import check_all_requirements

if TYPE_CHECKING:
    from literalai.client import LiteralClient

from literalai.context import active_steps_var, active_thread_var
from literalai.helper import ensure_values_serializable
from literalai.observability.generation import (
    ChatGeneration,
    CompletionGeneration,
    GenerationMessage,
    GenerationType,
)
from literalai.wrappers import AfterContext, BeforeContext, wrap_all

logger = logging.getLogger(__name__)

REQUIREMENTS = ["openai>=1.0.0"]

TO_WRAP = [
    {
        "module": "openai.resources.chat.completions",
        "object": "Completions",
        "method": "create",
        "metadata": {
            "type": GenerationType.CHAT,
        },
        "async": False,
    },
    {
        "module": "openai.resources.completions",
        "object": "Completions",
        "method": "create",
        "metadata": {
            "type": GenerationType.COMPLETION,
        },
        "async": False,
    },
    {
        "module": "openai.resources.chat.completions",
        "object": "AsyncCompletions",
        "method": "create",
        "metadata": {
            "type": GenerationType.CHAT,
        },
        "async": True,
    },
    {
        "module": "openai.resources.completions",
        "object": "AsyncCompletions",
        "method": "create",
        "metadata": {
            "type": GenerationType.COMPLETION,
        },
        "async": True,
    },
]

is_openai_instrumented = False


def instrument_openai(client: "LiteralClient", on_new_generation=None):
    """
    Instruments all OpenAI LLM calls to automatically send logs to Literal AI.
    """
    global is_openai_instrumented
    if is_openai_instrumented:
        return

    if not check_all_requirements(REQUIREMENTS):
        raise Exception(
            f"OpenAI instrumentation requirements not satisfied: {REQUIREMENTS}"
        )

    import inspect

    if callable(on_new_generation):
        sig = inspect.signature(on_new_generation)
        parameters = list(sig.parameters.values())

        if len(parameters) != 2:
            raise ValueError(
                "on_new_generation should take 2 parameters: generation and timing"
            )

    from openai import AsyncStream, Stream
    from openai.types.chat.chat_completion_chunk import ChoiceDelta

    def init_generation(generation_type: "GenerationType", kwargs):
        model = kwargs.get("model")
        tools = kwargs.get("tools")

        if generation_type == GenerationType.CHAT:
            orig_messages = kwargs.get("messages")

            messages = ensure_values_serializable(orig_messages)
            prompt_id = None
            variables = None

            for index, message in enumerate(messages):
                orig_message = orig_messages[index]
                if literal_prompt := getattr(orig_message, "__literal_prompt__", None):
                    prompt_id = literal_prompt.get("prompt_id")
                    variables = literal_prompt.get("variables")
                    message["uuid"] = literal_prompt.get("uuid")
                    message["templated"] = True

            settings = {
                "model": model,
                "frequency_penalty": kwargs.get("frequency_penalty"),
                "logit_bias": kwargs.get("logit_bias"),
                "logprobs": kwargs.get("logprobs"),
                "top_logprobs": kwargs.get("top_logprobs"),
                "max_tokens": kwargs.get("max_tokens"),
                "n": kwargs.get("n"),
                "presence_penalty": kwargs.get("presence_penalty"),
                "response_format": kwargs.get("response_format"),
                "seed": kwargs.get("seed"),
                "stop": kwargs.get("stop"),
                "stream": kwargs.get("stream"),
                "temperature": kwargs.get("temperature"),
                "top_p": kwargs.get("top_p"),
                "tool_choice": kwargs.get("tool_choice"),
            }
            settings = {k: v for k, v in settings.items() if v is not None}
            return ChatGeneration(
                prompt_id=prompt_id,
                variables=variables,
                provider=OPENAI_PROVIDER,
                model=model,
                tools=tools,
                settings=settings,
                messages=messages,
                metadata=kwargs.get("literalai_metadata"),
                tags=kwargs.get("literalai_tags"),
            )

        elif generation_type == GenerationType.COMPLETION:
            settings = {
                "model": model,
                "best_of": kwargs.get("best_of"),
                "echo": kwargs.get("echo"),
                "frequency_penalty": kwargs.get("frequency_penalty"),
                "logit_bias": kwargs.get("logit_bias"),
                "logprobs": kwargs.get("logprobs"),
                "max_tokens": kwargs.get("max_tokens"),
                "n": kwargs.get("n"),
                "presence_penalty": kwargs.get("presence_penalty"),
                "seed": kwargs.get("seed"),
                "stop": kwargs.get("stop"),
                "stream": kwargs.get("stream"),
                "suffix": kwargs.get("suffix"),
                "temperature": kwargs.get("temperature"),
                "top_p": kwargs.get("top_p"),
            }
            settings = {k: v for k, v in settings.items() if v is not None}
            return CompletionGeneration(
                provider=OPENAI_PROVIDER,
                model=model,
                settings=settings,
                prompt=kwargs.get("prompt"),
                metadata=kwargs.get("literalai_metadata"),
                tags=kwargs.get("literalai_tags"),
            )

    def update_step_after(
        generation: Union[ChatGeneration, CompletionGeneration], result
    ):
        if generation and isinstance(generation, ChatGeneration):
            generation.message_completion = result.choices[0].message.model_dump()

        elif generation and isinstance(generation, CompletionGeneration):
            if generation and generation.type == GenerationType.COMPLETION:
                generation.completion = result.choices[0].text

        if generation:
            generation.input_token_count = result.usage.prompt_tokens
            generation.output_token_count = result.usage.completion_tokens
            generation.token_count = result.usage.total_tokens

    def before_wrapper(metadata: Dict):
        def before(context: BeforeContext, *args, **kwargs):
            active_thread = active_thread_var.get()
            active_steps = active_steps_var.get()
            generation = init_generation(metadata["type"], kwargs)

            if (active_thread or active_steps) and not callable(on_new_generation):
                step = client.start_step(
                    name=context["original_func"].__name__, type="llm"
                )
                step.name = generation.model or OPENAI_PROVIDER
                if isinstance(generation, ChatGeneration):
                    step.input = {"content": generation.messages}
                else:
                    step.input = {"content": generation.prompt}

                context["step"] = step

            context["generation"] = generation
            context["start"] = time.time()

        return before

    def async_before_wrapper(metadata: Dict):
        async def before(context: BeforeContext, *args, **kwargs):
            active_thread = active_thread_var.get()
            active_steps = active_steps_var.get()
            generation = init_generation(metadata["type"], kwargs)

            if (active_thread or active_steps) and not callable(on_new_generation):
                step = client.start_step(
                    name=context["original_func"].__name__, type="llm"
                )
                step.name = generation.model or OPENAI_PROVIDER
                if isinstance(generation, ChatGeneration):
                    step.input = {"content": generation.messages}
                else:
                    step.input = {"content": generation.prompt}

                context["step"] = step

            context["generation"] = generation
            context["start"] = time.time()

        return before

    def process_delta(new_delta: ChoiceDelta, message_completion: GenerationMessage):
        if new_delta.function_call:
            if new_delta.function_call.name:
                message_completion["function_call"] = {
                    "name": new_delta.function_call.name
                }

            if not message_completion["function_call"]:
                return False

            if new_delta.function_call.arguments:
                if "arguments" not in message_completion["function_call"]:
                    message_completion["function_call"]["arguments"] = ""
                message_completion["function_call"][
                    "arguments"
                ] += new_delta.function_call.arguments
            return True
        elif new_delta.tool_calls:
            if "tool_calls" not in message_completion:
                message_completion["tool_calls"] = []
            delta_tool_call = new_delta.tool_calls[0]
            delta_function = delta_tool_call.function
            if not delta_function:
                return False
            if delta_function.name:
                message_completion["tool_calls"].append(  # type: ignore
                    {
                        "id": delta_tool_call.id,
                        "type": "function",
                        "function": {
                            "name": delta_function.name,
                            "arguments": "",
                        },
                    }
                )
            if delta_function.arguments:
                message_completion["tool_calls"][delta_tool_call.index]["function"][  # type: ignore
                    "arguments"
                ] += delta_function.arguments

            return True
        elif new_delta.content:
            if isinstance(message_completion["content"], str):
                message_completion["content"] += new_delta.content
                return True
        else:
            return False

    def streaming_response(
        generation: Union[ChatGeneration, CompletionGeneration],
        result,
        context: AfterContext,
    ):
        completion = ""
        message_completion = {
            "role": "assistant",
            "content": "",
        }  # type: GenerationMessage
        token_count = 0
        for chunk in result:
            if generation and isinstance(generation, ChatGeneration):
                if len(chunk.choices) > 0:
                    ok = process_delta(chunk.choices[0].delta, message_completion)
                    if not ok:
                        yield chunk
                        continue
                    if generation.tt_first_token is None:
                        generation.tt_first_token = (
                            time.time() - context["start"]
                        ) * 1000
                    token_count += 1
            elif generation and isinstance(generation, CompletionGeneration):
                if len(chunk.choices) > 0 and chunk.choices[0].text is not None:
                    if generation.tt_first_token is None:
                        generation.tt_first_token = (
                            time.time() - context["start"]
                        ) * 1000
                    token_count += 1
                    completion += chunk.choices[0].text

            if (
                generation
                and getattr(chunk, "model", None)
                and generation.model != chunk.model
            ):
                generation.model = chunk.model
                if generation.settings:
                    generation.settings["model"] = chunk.model

            yield chunk

        if generation:
            generation.duration = time.time() - context["start"]
            if generation.duration and token_count:
                generation.token_throughput_in_s = token_count / generation.duration
            if isinstance(generation, ChatGeneration):
                generation.message_completion = message_completion
            else:
                generation.completion = completion

        step = context.get("step")
        if callable(on_new_generation):
            on_new_generation(
                generation,
                {
                    "start": context["start"],
                    "end": time.time(),
                },
            )
        elif step:
            if isinstance(generation, ChatGeneration):
                step.output = generation.message_completion  # type: ignore
            else:
                step.output = {"content": generation.completion}
            step.generation = generation
            step.end()
        else:
            client.api.create_generation(generation)

    def after_wrapper(metadata: Dict):
        # Needs to be done in a separate function to avoid transforming all returned data into generators
        def after(result, context: AfterContext, *args, **kwargs):
            step = context.get("step")
            generation = context.get("generation")

            if not generation:
                return result

            if model := getattr(result, "model", None):
                generation.model = model
                if generation.settings:
                    generation.settings["model"] = model

            if isinstance(result, Stream):
                return streaming_response(generation, result, context)
            else:
                generation.duration = time.time() - context["start"]
                update_step_after(generation, result)

            if callable(on_new_generation):
                on_new_generation(
                    generation,
                    {
                        "start": context["start"],
                        "end": time.time(),
                    },
                )
            elif step:
                if isinstance(generation, ChatGeneration):
                    step.output = generation.message_completion  # type: ignore
                else:
                    step.output = {"content": generation.completion}
                step.generation = generation
                step.end()
            else:
                client.api.create_generation(generation)
            return result

        return after

    async def async_streaming_response(
        generation: Union[ChatGeneration, CompletionGeneration],
        result,
        context: AfterContext,
    ):
        completion = ""
        message_completion = {
            "role": "assistant",
            "content": "",
        }  # type: GenerationMessage
        token_count = 0
        async for chunk in result:
            if generation and isinstance(generation, ChatGeneration):
                if len(chunk.choices) > 0:
                    ok = process_delta(chunk.choices[0].delta, message_completion)
                    if not ok:
                        yield chunk
                        continue
                    if generation.tt_first_token is None:
                        generation.tt_first_token = (
                            time.time() - context["start"]
                        ) * 1000
                    token_count += 1
            elif generation and isinstance(generation, CompletionGeneration):
                if len(chunk.choices) > 0 and chunk.choices[0].text is not None:
                    if generation.tt_first_token is None:
                        generation.tt_first_token = (
                            time.time() - context["start"]
                        ) * 1000
                    token_count += 1
                    completion += chunk.choices[0].text

            if (
                generation
                and getattr(chunk, "model", None)
                and generation.model != chunk.model
            ):
                generation.model = chunk.model

            yield chunk

        if generation:
            generation.duration = time.time() - context["start"]
            if generation.duration and token_count:
                generation.token_throughput_in_s = token_count / generation.duration
            if isinstance(generation, ChatGeneration):
                generation.message_completion = message_completion
            else:
                generation.completion = completion

        step = context.get("step")
        if callable(on_new_generation):
            on_new_generation(
                generation,
                {
                    "start": context["start"],
                    "end": time.time(),
                },
            )
        elif step:
            if isinstance(generation, ChatGeneration):
                step.output = generation.message_completion  # type: ignore
            else:
                step.output = {"content": generation.completion}
            step.generation = generation
            step.end()
        else:
            client.api.create_generation(generation)

    def async_after_wrapper(metadata: Dict):
        async def after(result, context: AfterContext, *args, **kwargs):
            step = context.get("step")
            generation = context.get("generation")

            if not generation:
                return result

            if model := getattr(result, "model", None):
                generation.model = model
                if generation.settings:
                    generation.settings["model"] = model

            if isinstance(result, AsyncStream):
                return async_streaming_response(generation, result, context)
            else:
                generation.duration = time.time() - context["start"]
                update_step_after(generation, result)

            if callable(on_new_generation):
                on_new_generation(
                    generation,
                    {
                        "start": context["start"],
                        "end": time.time(),
                    },
                )
            elif step:
                if isinstance(generation, ChatGeneration):
                    step.output = generation.message_completion  # type: ignore
                else:
                    step.output = {"content": generation.completion}
                step.generation = generation
                step.end()
            else:
                client.api.create_generation(generation)
            return result

        return after

    wrap_all(
        TO_WRAP,
        before_wrapper,
        after_wrapper,
        async_before_wrapper,
        async_after_wrapper,
    )

    is_openai_instrumented = True
