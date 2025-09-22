import time
from typing import TYPE_CHECKING, AsyncGenerator, Dict, Generator, Union

from literalai.instrumentation import MISTRALAI_PROVIDER
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

REQUIREMENTS = ["mistralai>=1.0.0"]

APIS_TO_WRAP = [
    {
        "module": "mistralai.chat",
        "object": "Chat",
        "method": "complete",
        "metadata": {
            "type": GenerationType.CHAT,
        },
        "async": False,
    },
    {
        "module": "mistralai.chat",
        "object": "Chat",
        "method": "stream",
        "metadata": {
            "type": GenerationType.CHAT,
        },
        "async": False,
    },
    {
        "module": "mistralai.chat",
        "object": "Chat",
        "method": "complete_async",
        "metadata": {
            "type": GenerationType.CHAT,
        },
        "async": True,
    },
    {
        "module": "mistralai.chat",
        "object": "Chat",
        "method": "stream_async",
        "metadata": {
            "type": GenerationType.CHAT,
        },
        "async": True,
    },
    {
        "module": "mistralai.fim",
        "object": "Fim",
        "method": "complete",
        "metadata": {
            "type": GenerationType.COMPLETION,
        },
        "async": False,
    },
    {
        "module": "mistralai.fim",
        "object": "Fim",
        "method": "stream",
        "metadata": {
            "type": GenerationType.COMPLETION,
        },
        "async": False,
    },
    {
        "module": "mistralai.fim",
        "object": "Fim",
        "method": "complete_async",
        "metadata": {
            "type": GenerationType.COMPLETION,
        },
        "async": True,
    },
    {
        "module": "mistralai.fim",
        "object": "Fim",
        "method": "stream_async",
        "metadata": {
            "type": GenerationType.COMPLETION,
        },
        "async": True,
    },
]

is_mistralai_instrumented = False


def instrument_mistralai(client: "LiteralClient", on_new_generation=None):
    """
    Instruments all Mistral AI LLM calls to automatically send logs to Literal AI.
    """
    global is_mistralai_instrumented
    if is_mistralai_instrumented:
        return

    if not check_all_requirements(REQUIREMENTS):
        raise Exception(
            f"Mistral AI instrumentation requirements not satisfied: {REQUIREMENTS}"
        )

    import inspect

    if callable(on_new_generation):
        sig = inspect.signature(on_new_generation)
        parameters = list(sig.parameters.values())

        if len(parameters) != 2:
            raise ValueError(
                "on_new_generation should take 2 parameters: generation and timing"
            )

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
                "temperature": kwargs.get("temperature"),
                "top_p": kwargs.get("top_p"),
                "max_tokens": kwargs.get("max_tokens"),
                "stream": kwargs.get("stream"),
                "safe_prompt": kwargs.get("safe_prompt"),
                "random_seed": kwargs.get("random_seed"),
                "tool_choice": kwargs.get("tool_choice"),
                "response_format": kwargs.get("response_format"),
            }
            settings = {k: v for k, v in settings.items() if v is not None}
            return ChatGeneration(
                prompt_id=prompt_id,
                variables=variables,
                provider=MISTRALAI_PROVIDER,
                model=model,
                tools=tools,
                settings=settings,
                messages=messages,
                metadata=kwargs.get("literalai_metadata"),
                tags=kwargs.get("literalai_tags"),
            )
        elif generation_type == GenerationType.COMPLETION:
            settings = {
                "suffix": kwargs.get("suffix"),
                "model": model,
                "temperature": kwargs.get("temperature"),
                "top_p": kwargs.get("top_p"),
                "max_tokens": kwargs.get("max_tokens"),
                "min_tokens": kwargs.get("min_tokens"),
                "stream": kwargs.get("stream"),
                "random_seed": kwargs.get("random_seed"),
                "stop": kwargs.get("stop"),
            }
            settings = {k: v for k, v in settings.items() if v is not None}
            return CompletionGeneration(
                provider=MISTRALAI_PROVIDER,
                prompt=kwargs.get("prompt"),
                model=model,
                settings=settings,
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
                generation.completion = result.choices[0].message.content

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
                step.name = generation.model or MISTRALAI_PROVIDER
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
                step.name = generation.model or MISTRALAI_PROVIDER
                if isinstance(generation, ChatGeneration):
                    step.input = {"content": generation.messages}
                else:
                    step.input = {"content": generation.prompt}

                context["step"] = step

            context["generation"] = generation
            context["start"] = time.time()

        return before

    from mistralai import DeltaMessage

    def process_delta(new_delta: DeltaMessage, message_completion: GenerationMessage):
        if new_delta.tool_calls:
            if "tool_calls" not in message_completion:
                message_completion["tool_calls"] = []
            delta_tool_call = new_delta.tool_calls[0]  # type: ignore
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
                message_completion["tool_calls"][-1]["function"][  # type: ignore
                    "arguments"
                ] += delta_function.arguments

            return True
        elif new_delta.content:
            if isinstance(message_completion["content"], str):
                if isinstance(new_delta.content, str):
                    message_completion["content"] += new_delta.content
                    return True
        else:
            return False

    from mistralai import models

    def streaming_response(
        generation: Union[ChatGeneration, CompletionGeneration],
        result: Generator[models.CompletionEvent, None, None],
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
                if len(chunk.data.choices) > 0:
                    ok = process_delta(chunk.data.choices[0].delta, message_completion)
                    if not ok:
                        yield chunk
                        continue
                    if generation.tt_first_token is None:
                        generation.tt_first_token = (
                            time.time() - context["start"]
                        ) * 1000
                    token_count += 1
            elif generation and isinstance(generation, CompletionGeneration):
                if (
                    len(chunk.data.choices) > 0
                    and chunk.data.choices[0].delta.content is not None
                ):
                    if generation.tt_first_token is None:
                        generation.tt_first_token = (
                            time.time() - context["start"]
                        ) * 1000
                    token_count += 1
                    completion += str(chunk.data.choices[0].delta.content)

            if (
                generation
                and getattr(chunk, "model", None)
                and generation.model != chunk.data.model
            ):
                generation.model = chunk.data.model

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
            if isinstance(result, Generator):
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
        result: AsyncGenerator[models.CompletionEvent, None],
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
                if len(chunk.data.choices) > 0:
                    ok = process_delta(chunk.data.choices[0].delta, message_completion)
                    if not ok:
                        yield chunk
                        continue
                    if generation.tt_first_token is None:
                        generation.tt_first_token = (
                            time.time() - context["start"]
                        ) * 1000
                    token_count += 1
            elif generation and isinstance(generation, CompletionGeneration):
                if (
                    len(chunk.data.choices) > 0
                    and chunk.data.choices[0].delta is not None
                ):
                    if generation.tt_first_token is None:
                        generation.tt_first_token = (
                            time.time() - context["start"]
                        ) * 1000
                    token_count += 1
                    if isinstance(chunk.data.choices[0].delta.content, str):
                        completion += chunk.data.choices[0].delta.content or ""

            if (
                generation
                and getattr(chunk, "model", None)
                and generation.model != chunk.data.model
            ):
                generation.model = chunk.data.model

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

            if isinstance(result, AsyncGenerator):
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
        APIS_TO_WRAP,
        before_wrapper,
        after_wrapper,
        async_before_wrapper,
        async_after_wrapper,
    )

    is_mistralai_instrumented = True
