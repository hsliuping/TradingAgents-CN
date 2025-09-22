"""Google GenerativeAI Attributed Question and Answering (AQA) service.

The GenAI Semantic AQA API is a managed end to end service that allows
developers to create responses grounded on specified passages based on
a user query. For more information visit:
https://developers.generativeai.google/guide
"""

from typing import Any, List, Optional

import google.ai.generativelanguage as genai
from langchain_core.runnables import RunnableSerializable
from langchain_core.runnables.config import RunnableConfig
from pydantic import BaseModel, PrivateAttr

from . import _genai_extension as genaix


class AqaInput(BaseModel):
    """Input to `GenAIAqa.invoke`.

    Attributes:
        prompt: The user's inquiry.
        source_passages: A list of passage that the LLM should use only to
            answer the user's inquiry.
    """

    prompt: str
    source_passages: List[str]


class AqaOutput(BaseModel):
    """Output from `GenAIAqa.invoke`.

    Attributes:
        answer: The answer to the user's inquiry.
        attributed_passages: A list of passages that the LLM used to construct
            the answer.
        answerable_probability: The probability of the question being answered
            from the provided passages.
    """

    answer: str
    attributed_passages: List[str]
    answerable_probability: float


class _AqaModel(BaseModel):
    """Wrapper for Google's internal AQA model."""

    _client: genai.GenerativeServiceClient = PrivateAttr()
    _answer_style: int = PrivateAttr()
    _safety_settings: List[genai.SafetySetting] = PrivateAttr()
    _temperature: Optional[float] = PrivateAttr()

    def __init__(
        self,
        answer_style: int = genai.GenerateAnswerRequest.AnswerStyle.ABSTRACTIVE,
        safety_settings: List[genai.SafetySetting] = [],
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._client = genaix.build_generative_service()
        self._answer_style = answer_style
        self._safety_settings = safety_settings
        self._temperature = temperature

    def generate_answer(
        self,
        prompt: str,
        passages: List[str],
    ) -> genaix.GroundedAnswer:
        return genaix.generate_answer(
            prompt=prompt,
            passages=passages,
            client=self._client,
            answer_style=self._answer_style,
            safety_settings=self._safety_settings,
            temperature=self._temperature,
        )


class GenAIAqa(RunnableSerializable[AqaInput, AqaOutput]):
    """Google's Attributed Question and Answering service.

    Given a user's query and a list of passages, Google's server will return
    a response that is grounded to the provided list of passages. It will not
    base the response on parametric memory.

    Attributes:
        answer_style: keyword-only argument. See
            `google.ai.generativelanguage.AnswerStyle` for details.
    """

    # Actual type is .aqa_model.AqaModel.
    _client: _AqaModel = PrivateAttr()

    # Actual type is genai.AnswerStyle.
    # 1 = ABSTRACTIVE.
    # Cannot use the actual type here because user may not have
    # google.generativeai installed.
    answer_style: int = 1

    def __init__(self, **kwargs: Any) -> None:
        """Construct a Google Generative AI AQA model.

        All arguments are optional.

        Args:
            answer_style: See
              `google.ai.generativelanguage.GenerateAnswerRequest.AnswerStyle`.
            safety_settings: See `google.ai.generativelanguage.SafetySetting`.
            temperature: 0.0 to 1.0.
        """
        super().__init__(**kwargs)
        self._client = _AqaModel(**kwargs)

    def invoke(
        self, input: AqaInput, config: Optional[RunnableConfig] = None, **kwargs: Any
    ) -> AqaOutput:
        """Generates a grounded response using the provided passages."""

        response = self._client.generate_answer(
            prompt=input.prompt, passages=input.source_passages
        )

        return AqaOutput(
            answer=response.answer,
            attributed_passages=[
                passage.text for passage in response.attributed_passages
            ],
            answerable_probability=response.answerable_probability or 0.0,
        )
