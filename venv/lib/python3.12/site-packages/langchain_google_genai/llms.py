from __future__ import annotations

import logging
from difflib import get_close_matches
from typing import Any, Iterator, List, Optional

from langchain_core.callbacks import (
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import LangSmithParams
from langchain_core.language_models.llms import BaseLLM
from langchain_core.messages import HumanMessage
from langchain_core.outputs import Generation, GenerationChunk, LLMResult
from pydantic import ConfigDict, model_validator
from typing_extensions import Self

from langchain_google_genai._common import (
    _BaseGoogleGenerativeAI,
)
from langchain_google_genai.chat_models import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


class GoogleGenerativeAI(_BaseGoogleGenerativeAI, BaseLLM):
    """Google GenerativeAI models.

    Example:
        .. code-block:: python

            from langchain_google_genai import GoogleGenerativeAI
            llm = GoogleGenerativeAI(model="gemini-pro")
    """

    client: Any = None  #: :meta private:
    model_config = ConfigDict(
        populate_by_name=True,
    )

    def __init__(self, **kwargs: Any) -> None:
        """Needed for arg validation."""
        # Get all valid field names, including aliases
        valid_fields = set()
        for field_name, field_info in self.model_fields.items():
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
                    f"provided to GoogleGenerativeAI.{suggestion}"
                )
        super().__init__(**kwargs)

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        """Validates params and passes them to google-generativeai package."""

        if not any(self.model.startswith(prefix) for prefix in ("models/",)):
            self.model = f"models/{self.model}"

        self.client = ChatGoogleGenerativeAI(
            api_key=self.google_api_key,
            credentials=self.credentials,
            temperature=self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
            max_tokens=self.max_output_tokens,
            timeout=self.timeout,
            model=self.model,
            client_options=self.client_options,
            transport=self.transport,
            additional_headers=self.additional_headers,
            safety_settings=self.safety_settings,
        )

        return self

    def _get_ls_params(
        self, stop: Optional[List[str]] = None, **kwargs: Any
    ) -> LangSmithParams:
        """Get standard params for tracing."""
        ls_params = super()._get_ls_params(stop=stop, **kwargs)
        ls_params["ls_provider"] = "google_genai"

        models_prefix = "models/"
        ls_model_name = (
            self.model[len(models_prefix) :]
            if self.model and self.model.startswith(models_prefix)
            else self.model
        )
        ls_params["ls_model_name"] = ls_model_name

        if ls_max_tokens := kwargs.get("max_output_tokens", self.max_output_tokens):
            ls_params["ls_max_tokens"] = ls_max_tokens
        return ls_params

    def _generate(
        self,
        prompts: List[str],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        generations = []
        for prompt in prompts:
            chat_result = self.client._generate(
                [HumanMessage(content=prompt)],
                stop=stop,
                run_manager=run_manager,
                **kwargs,
            )
            generations.append(
                [
                    Generation(
                        text=g.message.content,
                        generation_info={
                            **g.generation_info,
                            **{"usage_metadata": g.message.usage_metadata},
                        },
                    )
                    for g in chat_result.generations
                ]
            )
        return LLMResult(generations=generations)

    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        for stream_chunk in self.client._stream(
            [HumanMessage(content=prompt)],
            stop=stop,
            run_manager=run_manager,
            **kwargs,
        ):
            chunk = GenerationChunk(text=stream_chunk.message.content)
            yield chunk
            if run_manager:
                run_manager.on_llm_new_token(
                    chunk.text,
                    chunk=chunk,
                    verbose=self.verbose,
                )

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "google_gemini"

    def get_num_tokens(self, text: str) -> int:
        """Get the number of tokens present in the text.

        Useful for checking if an input will fit in a model's context window.

        Args:
            text: The string input to tokenize.

        Returns:
            The integer number of tokens in the text.
        """
        return self.client.get_num_tokens(text)
