# -*- coding: utf-8 -*-
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from __future__ import annotations

from typing import MutableMapping, MutableSequence

import proto  # type: ignore

from google.ai.generativelanguage_v1alpha.types import citation
from google.ai.generativelanguage_v1alpha.types import content as gag_content
from google.ai.generativelanguage_v1alpha.types import retriever, safety

__protobuf__ = proto.module(
    package="google.ai.generativelanguage.v1alpha",
    manifest={
        "TaskType",
        "GenerateContentRequest",
        "PrebuiltVoiceConfig",
        "VoiceConfig",
        "SpeechConfig",
        "GenerationConfig",
        "SemanticRetrieverConfig",
        "GenerateContentResponse",
        "Candidate",
        "LogprobsResult",
        "AttributionSourceId",
        "GroundingAttribution",
        "RetrievalMetadata",
        "GroundingMetadata",
        "SearchEntryPoint",
        "GroundingChunk",
        "Segment",
        "GroundingSupport",
        "GenerateAnswerRequest",
        "GenerateAnswerResponse",
        "EmbedContentRequest",
        "ContentEmbedding",
        "EmbedContentResponse",
        "BatchEmbedContentsRequest",
        "BatchEmbedContentsResponse",
        "CountTokensRequest",
        "CountTokensResponse",
        "BidiGenerateContentSetup",
        "BidiGenerateContentClientContent",
        "BidiGenerateContentRealtimeInput",
        "BidiGenerateContentToolResponse",
        "BidiGenerateContentClientMessage",
        "BidiGenerateContentSetupComplete",
        "BidiGenerateContentServerContent",
        "BidiGenerateContentToolCall",
        "BidiGenerateContentToolCallCancellation",
        "BidiGenerateContentServerMessage",
    },
)


class TaskType(proto.Enum):
    r"""Type of task for which the embedding will be used.

    Values:
        TASK_TYPE_UNSPECIFIED (0):
            Unset value, which will default to one of the
            other enum values.
        RETRIEVAL_QUERY (1):
            Specifies the given text is a query in a
            search/retrieval setting.
        RETRIEVAL_DOCUMENT (2):
            Specifies the given text is a document from
            the corpus being searched.
        SEMANTIC_SIMILARITY (3):
            Specifies the given text will be used for
            STS.
        CLASSIFICATION (4):
            Specifies that the given text will be
            classified.
        CLUSTERING (5):
            Specifies that the embeddings will be used
            for clustering.
        QUESTION_ANSWERING (6):
            Specifies that the given text will be used
            for question answering.
        FACT_VERIFICATION (7):
            Specifies that the given text will be used
            for fact verification.
    """
    TASK_TYPE_UNSPECIFIED = 0
    RETRIEVAL_QUERY = 1
    RETRIEVAL_DOCUMENT = 2
    SEMANTIC_SIMILARITY = 3
    CLASSIFICATION = 4
    CLUSTERING = 5
    QUESTION_ANSWERING = 6
    FACT_VERIFICATION = 7


class GenerateContentRequest(proto.Message):
    r"""Request to generate a completion from the model.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        model (str):
            Required. The name of the ``Model`` to use for generating
            the completion.

            Format: ``models/{model}``.
        system_instruction (google.ai.generativelanguage_v1alpha.types.Content):
            Optional. Developer set `system
            instruction(s) <https://ai.google.dev/gemini-api/docs/system-instructions>`__.
            Currently, text only.

            This field is a member of `oneof`_ ``_system_instruction``.
        contents (MutableSequence[google.ai.generativelanguage_v1alpha.types.Content]):
            Required. The content of the current conversation with the
            model.

            For single-turn queries, this is a single instance. For
            multi-turn queries like
            `chat <https://ai.google.dev/gemini-api/docs/text-generation#chat>`__,
            this is a repeated field that contains the conversation
            history and the latest request.
        tools (MutableSequence[google.ai.generativelanguage_v1alpha.types.Tool]):
            Optional. A list of ``Tools`` the ``Model`` may use to
            generate the next response.

            A ``Tool`` is a piece of code that enables the system to
            interact with external systems to perform an action, or set
            of actions, outside of knowledge and scope of the ``Model``.
            Supported ``Tool``\ s are ``Function`` and
            ``code_execution``. Refer to the `Function
            calling <https://ai.google.dev/gemini-api/docs/function-calling>`__
            and the `Code
            execution <https://ai.google.dev/gemini-api/docs/code-execution>`__
            guides to learn more.
        tool_config (google.ai.generativelanguage_v1alpha.types.ToolConfig):
            Optional. Tool configuration for any ``Tool`` specified in
            the request. Refer to the `Function calling
            guide <https://ai.google.dev/gemini-api/docs/function-calling#function_calling_mode>`__
            for a usage example.
        safety_settings (MutableSequence[google.ai.generativelanguage_v1alpha.types.SafetySetting]):
            Optional. A list of unique ``SafetySetting`` instances for
            blocking unsafe content.

            This will be enforced on the
            ``GenerateContentRequest.contents`` and
            ``GenerateContentResponse.candidates``. There should not be
            more than one setting for each ``SafetyCategory`` type. The
            API will block any contents and responses that fail to meet
            the thresholds set by these settings. This list overrides
            the default settings for each ``SafetyCategory`` specified
            in the safety_settings. If there is no ``SafetySetting`` for
            a given ``SafetyCategory`` provided in the list, the API
            will use the default safety setting for that category. Harm
            categories HARM_CATEGORY_HATE_SPEECH,
            HARM_CATEGORY_SEXUALLY_EXPLICIT,
            HARM_CATEGORY_DANGEROUS_CONTENT, HARM_CATEGORY_HARASSMENT,
            HARM_CATEGORY_CIVIC_INTEGRITY are supported. Refer to the
            `guide <https://ai.google.dev/gemini-api/docs/safety-settings>`__
            for detailed information on available safety settings. Also
            refer to the `Safety
            guidance <https://ai.google.dev/gemini-api/docs/safety-guidance>`__
            to learn how to incorporate safety considerations in your AI
            applications.
        generation_config (google.ai.generativelanguage_v1alpha.types.GenerationConfig):
            Optional. Configuration options for model
            generation and outputs.

            This field is a member of `oneof`_ ``_generation_config``.
        cached_content (str):
            Optional. The name of the content
            `cached <https://ai.google.dev/gemini-api/docs/caching>`__
            to use as context to serve the prediction. Format:
            ``cachedContents/{cachedContent}``

            This field is a member of `oneof`_ ``_cached_content``.
    """

    model: str = proto.Field(
        proto.STRING,
        number=1,
    )
    system_instruction: gag_content.Content = proto.Field(
        proto.MESSAGE,
        number=8,
        optional=True,
        message=gag_content.Content,
    )
    contents: MutableSequence[gag_content.Content] = proto.RepeatedField(
        proto.MESSAGE,
        number=2,
        message=gag_content.Content,
    )
    tools: MutableSequence[gag_content.Tool] = proto.RepeatedField(
        proto.MESSAGE,
        number=5,
        message=gag_content.Tool,
    )
    tool_config: gag_content.ToolConfig = proto.Field(
        proto.MESSAGE,
        number=7,
        message=gag_content.ToolConfig,
    )
    safety_settings: MutableSequence[safety.SafetySetting] = proto.RepeatedField(
        proto.MESSAGE,
        number=3,
        message=safety.SafetySetting,
    )
    generation_config: "GenerationConfig" = proto.Field(
        proto.MESSAGE,
        number=4,
        optional=True,
        message="GenerationConfig",
    )
    cached_content: str = proto.Field(
        proto.STRING,
        number=9,
        optional=True,
    )


class PrebuiltVoiceConfig(proto.Message):
    r"""The configuration for the prebuilt speaker to use.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        voice_name (str):
            The name of the preset voice to use.

            This field is a member of `oneof`_ ``_voice_name``.
    """

    voice_name: str = proto.Field(
        proto.STRING,
        number=1,
        optional=True,
    )


class VoiceConfig(proto.Message):
    r"""The configuration for the voice to use.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        prebuilt_voice_config (google.ai.generativelanguage_v1alpha.types.PrebuiltVoiceConfig):
            The configuration for the prebuilt voice to
            use.

            This field is a member of `oneof`_ ``voice_config``.
    """

    prebuilt_voice_config: "PrebuiltVoiceConfig" = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof="voice_config",
        message="PrebuiltVoiceConfig",
    )


class SpeechConfig(proto.Message):
    r"""The speech generation config.

    Attributes:
        voice_config (google.ai.generativelanguage_v1alpha.types.VoiceConfig):
            The configuration for the speaker to use.
    """

    voice_config: "VoiceConfig" = proto.Field(
        proto.MESSAGE,
        number=1,
        message="VoiceConfig",
    )


class GenerationConfig(proto.Message):
    r"""Configuration options for model generation and outputs. Not
    all parameters are configurable for every model.


    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        candidate_count (int):
            Optional. Number of generated responses to
            return.
            Currently, this value can only be set to 1. If
            unset, this will default to 1.

            This field is a member of `oneof`_ ``_candidate_count``.
        stop_sequences (MutableSequence[str]):
            Optional. The set of character sequences (up to 5) that will
            stop output generation. If specified, the API will stop at
            the first appearance of a ``stop_sequence``. The stop
            sequence will not be included as part of the response.
        max_output_tokens (int):
            Optional. The maximum number of tokens to include in a
            response candidate.

            Note: The default value varies by model, see the
            ``Model.output_token_limit`` attribute of the ``Model``
            returned from the ``getModel`` function.

            This field is a member of `oneof`_ ``_max_output_tokens``.
        temperature (float):
            Optional. Controls the randomness of the output.

            Note: The default value varies by model, see the
            ``Model.temperature`` attribute of the ``Model`` returned
            from the ``getModel`` function.

            Values can range from [0.0, 2.0].

            This field is a member of `oneof`_ ``_temperature``.
        top_p (float):
            Optional. The maximum cumulative probability of tokens to
            consider when sampling.

            The model uses combined Top-k and Top-p (nucleus) sampling.

            Tokens are sorted based on their assigned probabilities so
            that only the most likely tokens are considered. Top-k
            sampling directly limits the maximum number of tokens to
            consider, while Nucleus sampling limits the number of tokens
            based on the cumulative probability.

            Note: The default value varies by ``Model`` and is specified
            by the\ ``Model.top_p`` attribute returned from the
            ``getModel`` function. An empty ``top_k`` attribute
            indicates that the model doesn't apply top-k sampling and
            doesn't allow setting ``top_k`` on requests.

            This field is a member of `oneof`_ ``_top_p``.
        top_k (int):
            Optional. The maximum number of tokens to consider when
            sampling.

            Gemini models use Top-p (nucleus) sampling or a combination
            of Top-k and nucleus sampling. Top-k sampling considers the
            set of ``top_k`` most probable tokens. Models running with
            nucleus sampling don't allow top_k setting.

            Note: The default value varies by ``Model`` and is specified
            by the\ ``Model.top_p`` attribute returned from the
            ``getModel`` function. An empty ``top_k`` attribute
            indicates that the model doesn't apply top-k sampling and
            doesn't allow setting ``top_k`` on requests.

            This field is a member of `oneof`_ ``_top_k``.
        response_mime_type (str):
            Optional. MIME type of the generated candidate text.
            Supported MIME types are: ``text/plain``: (default) Text
            output. ``application/json``: JSON response in the response
            candidates. ``text/x.enum``: ENUM as a string response in
            the response candidates. Refer to the
            `docs <https://ai.google.dev/gemini-api/docs/prompting_with_media#plain_text_formats>`__
            for a list of all supported text MIME types.
        response_schema (google.ai.generativelanguage_v1alpha.types.Schema):
            Optional. Output schema of the generated candidate text.
            Schemas must be a subset of the `OpenAPI
            schema <https://spec.openapis.org/oas/v3.0.3#schema>`__ and
            can be objects, primitives or arrays.

            If set, a compatible ``response_mime_type`` must also be
            set. Compatible MIME types: ``application/json``: Schema for
            JSON response. Refer to the `JSON text generation
            guide <https://ai.google.dev/gemini-api/docs/json-mode>`__
            for more details.
        presence_penalty (float):
            Optional. Presence penalty applied to the next token's
            logprobs if the token has already been seen in the response.

            This penalty is binary on/off and not dependant on the
            number of times the token is used (after the first). Use
            [frequency_penalty][google.ai.generativelanguage.v1alpha.GenerationConfig.frequency_penalty]
            for a penalty that increases with each use.

            A positive penalty will discourage the use of tokens that
            have already been used in the response, increasing the
            vocabulary.

            A negative penalty will encourage the use of tokens that
            have already been used in the response, decreasing the
            vocabulary.

            This field is a member of `oneof`_ ``_presence_penalty``.
        frequency_penalty (float):
            Optional. Frequency penalty applied to the next token's
            logprobs, multiplied by the number of times each token has
            been seen in the respponse so far.

            A positive penalty will discourage the use of tokens that
            have already been used, proportional to the number of times
            the token has been used: The more a token is used, the more
            dificult it is for the model to use that token again
            increasing the vocabulary of responses.

            Caution: A *negative* penalty will encourage the model to
            reuse tokens proportional to the number of times the token
            has been used. Small negative values will reduce the
            vocabulary of a response. Larger negative values will cause
            the model to start repeating a common token until it hits
            the
            [max_output_tokens][google.ai.generativelanguage.v1alpha.GenerationConfig.max_output_tokens]
            limit.

            This field is a member of `oneof`_ ``_frequency_penalty``.
        response_logprobs (bool):
            Optional. If true, export the logprobs
            results in response.

            This field is a member of `oneof`_ ``_response_logprobs``.
        logprobs (int):
            Optional. Only valid if
            [response_logprobs=True][google.ai.generativelanguage.v1alpha.GenerationConfig.response_logprobs].
            This sets the number of top logprobs to return at each
            decoding step in the
            [Candidate.logprobs_result][google.ai.generativelanguage.v1alpha.Candidate.logprobs_result].

            This field is a member of `oneof`_ ``_logprobs``.
        enable_enhanced_civic_answers (bool):
            Optional. Enables enhanced civic answers. It
            may not be available for all models.

            This field is a member of `oneof`_ ``_enable_enhanced_civic_answers``.
        response_modalities (MutableSequence[google.ai.generativelanguage_v1alpha.types.GenerationConfig.Modality]):
            Optional. The requested modalities of the
            response. Represents the set of modalities that
            the model can return, and should be expected in
            the response. This is an exact match to the
            modalities of the response.

            A model may have multiple combinations of
            supported modalities. If the requested
            modalities do not match any of the supported
            combinations, an error will be returned.

            An empty list is equivalent to requesting only
            text.
        speech_config (google.ai.generativelanguage_v1alpha.types.SpeechConfig):
            Optional. The speech generation config.

            This field is a member of `oneof`_ ``_speech_config``.
    """

    class Modality(proto.Enum):
        r"""Supported modalities of the response.

        Values:
            MODALITY_UNSPECIFIED (0):
                Default value.
            TEXT (1):
                Indicates the model should return text.
            IMAGE (2):
                Indicates the model should return images.
            AUDIO (3):
                Indicates the model should return audio.
        """
        MODALITY_UNSPECIFIED = 0
        TEXT = 1
        IMAGE = 2
        AUDIO = 3

    candidate_count: int = proto.Field(
        proto.INT32,
        number=1,
        optional=True,
    )
    stop_sequences: MutableSequence[str] = proto.RepeatedField(
        proto.STRING,
        number=2,
    )
    max_output_tokens: int = proto.Field(
        proto.INT32,
        number=4,
        optional=True,
    )
    temperature: float = proto.Field(
        proto.FLOAT,
        number=5,
        optional=True,
    )
    top_p: float = proto.Field(
        proto.FLOAT,
        number=6,
        optional=True,
    )
    top_k: int = proto.Field(
        proto.INT32,
        number=7,
        optional=True,
    )
    response_mime_type: str = proto.Field(
        proto.STRING,
        number=13,
    )
    response_schema: gag_content.Schema = proto.Field(
        proto.MESSAGE,
        number=14,
        message=gag_content.Schema,
    )
    presence_penalty: float = proto.Field(
        proto.FLOAT,
        number=15,
        optional=True,
    )
    frequency_penalty: float = proto.Field(
        proto.FLOAT,
        number=16,
        optional=True,
    )
    response_logprobs: bool = proto.Field(
        proto.BOOL,
        number=17,
        optional=True,
    )
    logprobs: int = proto.Field(
        proto.INT32,
        number=18,
        optional=True,
    )
    enable_enhanced_civic_answers: bool = proto.Field(
        proto.BOOL,
        number=19,
        optional=True,
    )
    response_modalities: MutableSequence[Modality] = proto.RepeatedField(
        proto.ENUM,
        number=20,
        enum=Modality,
    )
    speech_config: "SpeechConfig" = proto.Field(
        proto.MESSAGE,
        number=21,
        optional=True,
        message="SpeechConfig",
    )


class SemanticRetrieverConfig(proto.Message):
    r"""Configuration for retrieving grounding content from a ``Corpus`` or
    ``Document`` created using the Semantic Retriever API.


    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        source (str):
            Required. Name of the resource for retrieval. Example:
            ``corpora/123`` or ``corpora/123/documents/abc``.
        query (google.ai.generativelanguage_v1alpha.types.Content):
            Required. Query to use for matching ``Chunk``\ s in the
            given resource by similarity.
        metadata_filters (MutableSequence[google.ai.generativelanguage_v1alpha.types.MetadataFilter]):
            Optional. Filters for selecting ``Document``\ s and/or
            ``Chunk``\ s from the resource.
        max_chunks_count (int):
            Optional. Maximum number of relevant ``Chunk``\ s to
            retrieve.

            This field is a member of `oneof`_ ``_max_chunks_count``.
        minimum_relevance_score (float):
            Optional. Minimum relevance score for retrieved relevant
            ``Chunk``\ s.

            This field is a member of `oneof`_ ``_minimum_relevance_score``.
    """

    source: str = proto.Field(
        proto.STRING,
        number=1,
    )
    query: gag_content.Content = proto.Field(
        proto.MESSAGE,
        number=2,
        message=gag_content.Content,
    )
    metadata_filters: MutableSequence[retriever.MetadataFilter] = proto.RepeatedField(
        proto.MESSAGE,
        number=3,
        message=retriever.MetadataFilter,
    )
    max_chunks_count: int = proto.Field(
        proto.INT32,
        number=4,
        optional=True,
    )
    minimum_relevance_score: float = proto.Field(
        proto.FLOAT,
        number=5,
        optional=True,
    )


class GenerateContentResponse(proto.Message):
    r"""Response from the model supporting multiple candidate responses.

    Safety ratings and content filtering are reported for both prompt in
    ``GenerateContentResponse.prompt_feedback`` and for each candidate
    in ``finish_reason`` and in ``safety_ratings``. The API:

    -  Returns either all requested candidates or none of them
    -  Returns no candidates at all only if there was something wrong
       with the prompt (check ``prompt_feedback``)
    -  Reports feedback on each candidate in ``finish_reason`` and
       ``safety_ratings``.

    Attributes:
        candidates (MutableSequence[google.ai.generativelanguage_v1alpha.types.Candidate]):
            Candidate responses from the model.
        prompt_feedback (google.ai.generativelanguage_v1alpha.types.GenerateContentResponse.PromptFeedback):
            Returns the prompt's feedback related to the
            content filters.
        usage_metadata (google.ai.generativelanguage_v1alpha.types.GenerateContentResponse.UsageMetadata):
            Output only. Metadata on the generation
            requests' token usage.
        model_version (str):
            Output only. The model version used to
            generate the response.
    """

    class PromptFeedback(proto.Message):
        r"""A set of the feedback metadata the prompt specified in
        ``GenerateContentRequest.content``.

        Attributes:
            block_reason (google.ai.generativelanguage_v1alpha.types.GenerateContentResponse.PromptFeedback.BlockReason):
                Optional. If set, the prompt was blocked and
                no candidates are returned. Rephrase the prompt.
            safety_ratings (MutableSequence[google.ai.generativelanguage_v1alpha.types.SafetyRating]):
                Ratings for safety of the prompt.
                There is at most one rating per category.
        """

        class BlockReason(proto.Enum):
            r"""Specifies the reason why the prompt was blocked.

            Values:
                BLOCK_REASON_UNSPECIFIED (0):
                    Default value. This value is unused.
                SAFETY (1):
                    Prompt was blocked due to safety reasons. Inspect
                    ``safety_ratings`` to understand which safety category
                    blocked it.
                OTHER (2):
                    Prompt was blocked due to unknown reasons.
                BLOCKLIST (3):
                    Prompt was blocked due to the terms which are
                    included from the terminology blocklist.
                PROHIBITED_CONTENT (4):
                    Prompt was blocked due to prohibited content.
                IMAGE_SAFETY (5):
                    Candidates blocked due to unsafe image
                    generation content.
            """
            BLOCK_REASON_UNSPECIFIED = 0
            SAFETY = 1
            OTHER = 2
            BLOCKLIST = 3
            PROHIBITED_CONTENT = 4
            IMAGE_SAFETY = 5

        block_reason: "GenerateContentResponse.PromptFeedback.BlockReason" = (
            proto.Field(
                proto.ENUM,
                number=1,
                enum="GenerateContentResponse.PromptFeedback.BlockReason",
            )
        )
        safety_ratings: MutableSequence[safety.SafetyRating] = proto.RepeatedField(
            proto.MESSAGE,
            number=2,
            message=safety.SafetyRating,
        )

    class UsageMetadata(proto.Message):
        r"""Metadata on the generation request's token usage.

        Attributes:
            prompt_token_count (int):
                Number of tokens in the prompt. When ``cached_content`` is
                set, this is still the total effective prompt size meaning
                this includes the number of tokens in the cached content.
            cached_content_token_count (int):
                Number of tokens in the cached part of the
                prompt (the cached content)
            candidates_token_count (int):
                Total number of tokens across all the
                generated response candidates.
            total_token_count (int):
                Total token count for the generation request
                (prompt + response candidates).
        """

        prompt_token_count: int = proto.Field(
            proto.INT32,
            number=1,
        )
        cached_content_token_count: int = proto.Field(
            proto.INT32,
            number=4,
        )
        candidates_token_count: int = proto.Field(
            proto.INT32,
            number=2,
        )
        total_token_count: int = proto.Field(
            proto.INT32,
            number=3,
        )

    candidates: MutableSequence["Candidate"] = proto.RepeatedField(
        proto.MESSAGE,
        number=1,
        message="Candidate",
    )
    prompt_feedback: PromptFeedback = proto.Field(
        proto.MESSAGE,
        number=2,
        message=PromptFeedback,
    )
    usage_metadata: UsageMetadata = proto.Field(
        proto.MESSAGE,
        number=3,
        message=UsageMetadata,
    )
    model_version: str = proto.Field(
        proto.STRING,
        number=4,
    )


class Candidate(proto.Message):
    r"""A response candidate generated from the model.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        index (int):
            Output only. Index of the candidate in the
            list of response candidates.

            This field is a member of `oneof`_ ``_index``.
        content (google.ai.generativelanguage_v1alpha.types.Content):
            Output only. Generated content returned from
            the model.
        finish_reason (google.ai.generativelanguage_v1alpha.types.Candidate.FinishReason):
            Optional. Output only. The reason why the
            model stopped generating tokens.
            If empty, the model has not stopped generating
            tokens.
        safety_ratings (MutableSequence[google.ai.generativelanguage_v1alpha.types.SafetyRating]):
            List of ratings for the safety of a response
            candidate.
            There is at most one rating per category.
        citation_metadata (google.ai.generativelanguage_v1alpha.types.CitationMetadata):
            Output only. Citation information for model-generated
            candidate.

            This field may be populated with recitation information for
            any text included in the ``content``. These are passages
            that are "recited" from copyrighted material in the
            foundational LLM's training data.
        token_count (int):
            Output only. Token count for this candidate.
        grounding_attributions (MutableSequence[google.ai.generativelanguage_v1alpha.types.GroundingAttribution]):
            Output only. Attribution information for sources that
            contributed to a grounded answer.

            This field is populated for ``GenerateAnswer`` calls.
        grounding_metadata (google.ai.generativelanguage_v1alpha.types.GroundingMetadata):
            Output only. Grounding metadata for the candidate.

            This field is populated for ``GenerateContent`` calls.
        avg_logprobs (float):
            Output only. Average log probability score of
            the candidate.
        logprobs_result (google.ai.generativelanguage_v1alpha.types.LogprobsResult):
            Output only. Log-likelihood scores for the
            response tokens and top tokens
    """

    class FinishReason(proto.Enum):
        r"""Defines the reason why the model stopped generating tokens.

        Values:
            FINISH_REASON_UNSPECIFIED (0):
                Default value. This value is unused.
            STOP (1):
                Natural stop point of the model or provided
                stop sequence.
            MAX_TOKENS (2):
                The maximum number of tokens as specified in
                the request was reached.
            SAFETY (3):
                The response candidate content was flagged
                for safety reasons.
            RECITATION (4):
                The response candidate content was flagged
                for recitation reasons.
            LANGUAGE (6):
                The response candidate content was flagged
                for using an unsupported language.
            OTHER (5):
                Unknown reason.
            BLOCKLIST (7):
                Token generation stopped because the content
                contains forbidden terms.
            PROHIBITED_CONTENT (8):
                Token generation stopped for potentially
                containing prohibited content.
            SPII (9):
                Token generation stopped because the content
                potentially contains Sensitive Personally
                Identifiable Information (SPII).
            MALFORMED_FUNCTION_CALL (10):
                The function call generated by the model is
                invalid.
            IMAGE_SAFETY (11):
                Token generation stopped because generated
                images contain safety violations.
        """
        FINISH_REASON_UNSPECIFIED = 0
        STOP = 1
        MAX_TOKENS = 2
        SAFETY = 3
        RECITATION = 4
        LANGUAGE = 6
        OTHER = 5
        BLOCKLIST = 7
        PROHIBITED_CONTENT = 8
        SPII = 9
        MALFORMED_FUNCTION_CALL = 10
        IMAGE_SAFETY = 11

    index: int = proto.Field(
        proto.INT32,
        number=3,
        optional=True,
    )
    content: gag_content.Content = proto.Field(
        proto.MESSAGE,
        number=1,
        message=gag_content.Content,
    )
    finish_reason: FinishReason = proto.Field(
        proto.ENUM,
        number=2,
        enum=FinishReason,
    )
    safety_ratings: MutableSequence[safety.SafetyRating] = proto.RepeatedField(
        proto.MESSAGE,
        number=5,
        message=safety.SafetyRating,
    )
    citation_metadata: citation.CitationMetadata = proto.Field(
        proto.MESSAGE,
        number=6,
        message=citation.CitationMetadata,
    )
    token_count: int = proto.Field(
        proto.INT32,
        number=7,
    )
    grounding_attributions: MutableSequence[
        "GroundingAttribution"
    ] = proto.RepeatedField(
        proto.MESSAGE,
        number=8,
        message="GroundingAttribution",
    )
    grounding_metadata: "GroundingMetadata" = proto.Field(
        proto.MESSAGE,
        number=9,
        message="GroundingMetadata",
    )
    avg_logprobs: float = proto.Field(
        proto.DOUBLE,
        number=10,
    )
    logprobs_result: "LogprobsResult" = proto.Field(
        proto.MESSAGE,
        number=11,
        message="LogprobsResult",
    )


class LogprobsResult(proto.Message):
    r"""Logprobs Result

    Attributes:
        top_candidates (MutableSequence[google.ai.generativelanguage_v1alpha.types.LogprobsResult.TopCandidates]):
            Length = total number of decoding steps.
        chosen_candidates (MutableSequence[google.ai.generativelanguage_v1alpha.types.LogprobsResult.Candidate]):
            Length = total number of decoding steps. The chosen
            candidates may or may not be in top_candidates.
    """

    class Candidate(proto.Message):
        r"""Candidate for the logprobs token and score.

        .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

        Attributes:
            token (str):
                The candidate’s token string value.

                This field is a member of `oneof`_ ``_token``.
            token_id (int):
                The candidate’s token id value.

                This field is a member of `oneof`_ ``_token_id``.
            log_probability (float):
                The candidate's log probability.

                This field is a member of `oneof`_ ``_log_probability``.
        """

        token: str = proto.Field(
            proto.STRING,
            number=1,
            optional=True,
        )
        token_id: int = proto.Field(
            proto.INT32,
            number=3,
            optional=True,
        )
        log_probability: float = proto.Field(
            proto.FLOAT,
            number=2,
            optional=True,
        )

    class TopCandidates(proto.Message):
        r"""Candidates with top log probabilities at each decoding step.

        Attributes:
            candidates (MutableSequence[google.ai.generativelanguage_v1alpha.types.LogprobsResult.Candidate]):
                Sorted by log probability in descending
                order.
        """

        candidates: MutableSequence["LogprobsResult.Candidate"] = proto.RepeatedField(
            proto.MESSAGE,
            number=1,
            message="LogprobsResult.Candidate",
        )

    top_candidates: MutableSequence[TopCandidates] = proto.RepeatedField(
        proto.MESSAGE,
        number=1,
        message=TopCandidates,
    )
    chosen_candidates: MutableSequence[Candidate] = proto.RepeatedField(
        proto.MESSAGE,
        number=2,
        message=Candidate,
    )


class AttributionSourceId(proto.Message):
    r"""Identifier for the source contributing to this attribution.

    This message has `oneof`_ fields (mutually exclusive fields).
    For each oneof, at most one member field can be set at the same time.
    Setting any member of the oneof automatically clears all other
    members.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        grounding_passage (google.ai.generativelanguage_v1alpha.types.AttributionSourceId.GroundingPassageId):
            Identifier for an inline passage.

            This field is a member of `oneof`_ ``source``.
        semantic_retriever_chunk (google.ai.generativelanguage_v1alpha.types.AttributionSourceId.SemanticRetrieverChunk):
            Identifier for a ``Chunk`` fetched via Semantic Retriever.

            This field is a member of `oneof`_ ``source``.
    """

    class GroundingPassageId(proto.Message):
        r"""Identifier for a part within a ``GroundingPassage``.

        Attributes:
            passage_id (str):
                Output only. ID of the passage matching the
                ``GenerateAnswerRequest``'s ``GroundingPassage.id``.
            part_index (int):
                Output only. Index of the part within the
                ``GenerateAnswerRequest``'s ``GroundingPassage.content``.
        """

        passage_id: str = proto.Field(
            proto.STRING,
            number=1,
        )
        part_index: int = proto.Field(
            proto.INT32,
            number=2,
        )

    class SemanticRetrieverChunk(proto.Message):
        r"""Identifier for a ``Chunk`` retrieved via Semantic Retriever
        specified in the ``GenerateAnswerRequest`` using
        ``SemanticRetrieverConfig``.

        Attributes:
            source (str):
                Output only. Name of the source matching the request's
                ``SemanticRetrieverConfig.source``. Example: ``corpora/123``
                or ``corpora/123/documents/abc``
            chunk (str):
                Output only. Name of the ``Chunk`` containing the attributed
                text. Example: ``corpora/123/documents/abc/chunks/xyz``
        """

        source: str = proto.Field(
            proto.STRING,
            number=1,
        )
        chunk: str = proto.Field(
            proto.STRING,
            number=2,
        )

    grounding_passage: GroundingPassageId = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof="source",
        message=GroundingPassageId,
    )
    semantic_retriever_chunk: SemanticRetrieverChunk = proto.Field(
        proto.MESSAGE,
        number=2,
        oneof="source",
        message=SemanticRetrieverChunk,
    )


class GroundingAttribution(proto.Message):
    r"""Attribution for a source that contributed to an answer.

    Attributes:
        source_id (google.ai.generativelanguage_v1alpha.types.AttributionSourceId):
            Output only. Identifier for the source
            contributing to this attribution.
        content (google.ai.generativelanguage_v1alpha.types.Content):
            Grounding source content that makes up this
            attribution.
    """

    source_id: "AttributionSourceId" = proto.Field(
        proto.MESSAGE,
        number=3,
        message="AttributionSourceId",
    )
    content: gag_content.Content = proto.Field(
        proto.MESSAGE,
        number=2,
        message=gag_content.Content,
    )


class RetrievalMetadata(proto.Message):
    r"""Metadata related to retrieval in the grounding flow.

    Attributes:
        google_search_dynamic_retrieval_score (float):
            Optional. Score indicating how likely information from
            google search could help answer the prompt. The score is in
            the range [0, 1], where 0 is the least likely and 1 is the
            most likely. This score is only populated when google search
            grounding and dynamic retrieval is enabled. It will be
            compared to the threshold to determine whether to trigger
            google search.
    """

    google_search_dynamic_retrieval_score: float = proto.Field(
        proto.FLOAT,
        number=2,
    )


class GroundingMetadata(proto.Message):
    r"""Metadata returned to client when grounding is enabled.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        search_entry_point (google.ai.generativelanguage_v1alpha.types.SearchEntryPoint):
            Optional. Google search entry for the
            following-up web searches.

            This field is a member of `oneof`_ ``_search_entry_point``.
        grounding_chunks (MutableSequence[google.ai.generativelanguage_v1alpha.types.GroundingChunk]):
            List of supporting references retrieved from
            specified grounding source.
        grounding_supports (MutableSequence[google.ai.generativelanguage_v1alpha.types.GroundingSupport]):
            List of grounding support.
        retrieval_metadata (google.ai.generativelanguage_v1alpha.types.RetrievalMetadata):
            Metadata related to retrieval in the
            grounding flow.

            This field is a member of `oneof`_ ``_retrieval_metadata``.
        web_search_queries (MutableSequence[str]):
            Web search queries for the following-up web
            search.
    """

    search_entry_point: "SearchEntryPoint" = proto.Field(
        proto.MESSAGE,
        number=1,
        optional=True,
        message="SearchEntryPoint",
    )
    grounding_chunks: MutableSequence["GroundingChunk"] = proto.RepeatedField(
        proto.MESSAGE,
        number=2,
        message="GroundingChunk",
    )
    grounding_supports: MutableSequence["GroundingSupport"] = proto.RepeatedField(
        proto.MESSAGE,
        number=3,
        message="GroundingSupport",
    )
    retrieval_metadata: "RetrievalMetadata" = proto.Field(
        proto.MESSAGE,
        number=4,
        optional=True,
        message="RetrievalMetadata",
    )
    web_search_queries: MutableSequence[str] = proto.RepeatedField(
        proto.STRING,
        number=5,
    )


class SearchEntryPoint(proto.Message):
    r"""Google search entry point.

    Attributes:
        rendered_content (str):
            Optional. Web content snippet that can be
            embedded in a web page or an app webview.
        sdk_blob (bytes):
            Optional. Base64 encoded JSON representing
            array of <search term, search url> tuple.
    """

    rendered_content: str = proto.Field(
        proto.STRING,
        number=1,
    )
    sdk_blob: bytes = proto.Field(
        proto.BYTES,
        number=2,
    )


class GroundingChunk(proto.Message):
    r"""Grounding chunk.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        web (google.ai.generativelanguage_v1alpha.types.GroundingChunk.Web):
            Grounding chunk from the web.

            This field is a member of `oneof`_ ``chunk_type``.
    """

    class Web(proto.Message):
        r"""Chunk from the web.

        .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

        Attributes:
            uri (str):
                URI reference of the chunk.

                This field is a member of `oneof`_ ``_uri``.
            title (str):
                Title of the chunk.

                This field is a member of `oneof`_ ``_title``.
        """

        uri: str = proto.Field(
            proto.STRING,
            number=1,
            optional=True,
        )
        title: str = proto.Field(
            proto.STRING,
            number=2,
            optional=True,
        )

    web: Web = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof="chunk_type",
        message=Web,
    )


class Segment(proto.Message):
    r"""Segment of the content.

    Attributes:
        part_index (int):
            Output only. The index of a Part object
            within its parent Content object.
        start_index (int):
            Output only. Start index in the given Part,
            measured in bytes. Offset from the start of the
            Part, inclusive, starting at zero.
        end_index (int):
            Output only. End index in the given Part,
            measured in bytes. Offset from the start of the
            Part, exclusive, starting at zero.
        text (str):
            Output only. The text corresponding to the
            segment from the response.
    """

    part_index: int = proto.Field(
        proto.INT32,
        number=1,
    )
    start_index: int = proto.Field(
        proto.INT32,
        number=2,
    )
    end_index: int = proto.Field(
        proto.INT32,
        number=3,
    )
    text: str = proto.Field(
        proto.STRING,
        number=4,
    )


class GroundingSupport(proto.Message):
    r"""Grounding support.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        segment (google.ai.generativelanguage_v1alpha.types.Segment):
            Segment of the content this support belongs
            to.

            This field is a member of `oneof`_ ``_segment``.
        grounding_chunk_indices (MutableSequence[int]):
            A list of indices (into 'grounding_chunk') specifying the
            citations associated with the claim. For instance [1,3,4]
            means that grounding_chunk[1], grounding_chunk[3],
            grounding_chunk[4] are the retrieved content attributed to
            the claim.
        confidence_scores (MutableSequence[float]):
            Confidence score of the support references. Ranges from 0 to
            1. 1 is the most confident. This list must have the same
            size as the grounding_chunk_indices.
    """

    segment: "Segment" = proto.Field(
        proto.MESSAGE,
        number=1,
        optional=True,
        message="Segment",
    )
    grounding_chunk_indices: MutableSequence[int] = proto.RepeatedField(
        proto.INT32,
        number=2,
    )
    confidence_scores: MutableSequence[float] = proto.RepeatedField(
        proto.FLOAT,
        number=3,
    )


class GenerateAnswerRequest(proto.Message):
    r"""Request to generate a grounded answer from the ``Model``.

    This message has `oneof`_ fields (mutually exclusive fields).
    For each oneof, at most one member field can be set at the same time.
    Setting any member of the oneof automatically clears all other
    members.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        inline_passages (google.ai.generativelanguage_v1alpha.types.GroundingPassages):
            Passages provided inline with the request.

            This field is a member of `oneof`_ ``grounding_source``.
        semantic_retriever (google.ai.generativelanguage_v1alpha.types.SemanticRetrieverConfig):
            Content retrieved from resources created via
            the Semantic Retriever API.

            This field is a member of `oneof`_ ``grounding_source``.
        model (str):
            Required. The name of the ``Model`` to use for generating
            the grounded response.

            Format: ``model=models/{model}``.
        contents (MutableSequence[google.ai.generativelanguage_v1alpha.types.Content]):
            Required. The content of the current conversation with the
            ``Model``. For single-turn queries, this is a single
            question to answer. For multi-turn queries, this is a
            repeated field that contains conversation history and the
            last ``Content`` in the list containing the question.

            Note: ``GenerateAnswer`` only supports queries in English.
        answer_style (google.ai.generativelanguage_v1alpha.types.GenerateAnswerRequest.AnswerStyle):
            Required. Style in which answers should be
            returned.
        safety_settings (MutableSequence[google.ai.generativelanguage_v1alpha.types.SafetySetting]):
            Optional. A list of unique ``SafetySetting`` instances for
            blocking unsafe content.

            This will be enforced on the
            ``GenerateAnswerRequest.contents`` and
            ``GenerateAnswerResponse.candidate``. There should not be
            more than one setting for each ``SafetyCategory`` type. The
            API will block any contents and responses that fail to meet
            the thresholds set by these settings. This list overrides
            the default settings for each ``SafetyCategory`` specified
            in the safety_settings. If there is no ``SafetySetting`` for
            a given ``SafetyCategory`` provided in the list, the API
            will use the default safety setting for that category. Harm
            categories HARM_CATEGORY_HATE_SPEECH,
            HARM_CATEGORY_SEXUALLY_EXPLICIT,
            HARM_CATEGORY_DANGEROUS_CONTENT, HARM_CATEGORY_HARASSMENT
            are supported. Refer to the
            `guide <https://ai.google.dev/gemini-api/docs/safety-settings>`__
            for detailed information on available safety settings. Also
            refer to the `Safety
            guidance <https://ai.google.dev/gemini-api/docs/safety-guidance>`__
            to learn how to incorporate safety considerations in your AI
            applications.
        temperature (float):
            Optional. Controls the randomness of the output.

            Values can range from [0.0,1.0], inclusive. A value closer
            to 1.0 will produce responses that are more varied and
            creative, while a value closer to 0.0 will typically result
            in more straightforward responses from the model. A low
            temperature (~0.2) is usually recommended for
            Attributed-Question-Answering use cases.

            This field is a member of `oneof`_ ``_temperature``.
    """

    class AnswerStyle(proto.Enum):
        r"""Style for grounded answers.

        Values:
            ANSWER_STYLE_UNSPECIFIED (0):
                Unspecified answer style.
            ABSTRACTIVE (1):
                Succint but abstract style.
            EXTRACTIVE (2):
                Very brief and extractive style.
            VERBOSE (3):
                Verbose style including extra details. The
                response may be formatted as a sentence,
                paragraph, multiple paragraphs, or bullet
                points, etc.
        """
        ANSWER_STYLE_UNSPECIFIED = 0
        ABSTRACTIVE = 1
        EXTRACTIVE = 2
        VERBOSE = 3

    inline_passages: gag_content.GroundingPassages = proto.Field(
        proto.MESSAGE,
        number=6,
        oneof="grounding_source",
        message=gag_content.GroundingPassages,
    )
    semantic_retriever: "SemanticRetrieverConfig" = proto.Field(
        proto.MESSAGE,
        number=7,
        oneof="grounding_source",
        message="SemanticRetrieverConfig",
    )
    model: str = proto.Field(
        proto.STRING,
        number=1,
    )
    contents: MutableSequence[gag_content.Content] = proto.RepeatedField(
        proto.MESSAGE,
        number=2,
        message=gag_content.Content,
    )
    answer_style: AnswerStyle = proto.Field(
        proto.ENUM,
        number=5,
        enum=AnswerStyle,
    )
    safety_settings: MutableSequence[safety.SafetySetting] = proto.RepeatedField(
        proto.MESSAGE,
        number=3,
        message=safety.SafetySetting,
    )
    temperature: float = proto.Field(
        proto.FLOAT,
        number=4,
        optional=True,
    )


class GenerateAnswerResponse(proto.Message):
    r"""Response from the model for a grounded answer.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        answer (google.ai.generativelanguage_v1alpha.types.Candidate):
            Candidate answer from the model.

            Note: The model *always* attempts to provide a grounded
            answer, even when the answer is unlikely to be answerable
            from the given passages. In that case, a low-quality or
            ungrounded answer may be provided, along with a low
            ``answerable_probability``.
        answerable_probability (float):
            Output only. The model's estimate of the probability that
            its answer is correct and grounded in the input passages.

            A low ``answerable_probability`` indicates that the answer
            might not be grounded in the sources.

            When ``answerable_probability`` is low, you may want to:

            -  Display a message to the effect of "We couldn’t answer
               that question" to the user.
            -  Fall back to a general-purpose LLM that answers the
               question from world knowledge. The threshold and nature
               of such fallbacks will depend on individual use cases.
               ``0.5`` is a good starting threshold.

            This field is a member of `oneof`_ ``_answerable_probability``.
        input_feedback (google.ai.generativelanguage_v1alpha.types.GenerateAnswerResponse.InputFeedback):
            Output only. Feedback related to the input data used to
            answer the question, as opposed to the model-generated
            response to the question.

            The input data can be one or more of the following:

            -  Question specified by the last entry in
               ``GenerateAnswerRequest.content``
            -  Conversation history specified by the other entries in
               ``GenerateAnswerRequest.content``
            -  Grounding sources
               (``GenerateAnswerRequest.semantic_retriever`` or
               ``GenerateAnswerRequest.inline_passages``)

            This field is a member of `oneof`_ ``_input_feedback``.
    """

    class InputFeedback(proto.Message):
        r"""Feedback related to the input data used to answer the
        question, as opposed to the model-generated response to the
        question.


        .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

        Attributes:
            block_reason (google.ai.generativelanguage_v1alpha.types.GenerateAnswerResponse.InputFeedback.BlockReason):
                Optional. If set, the input was blocked and
                no candidates are returned. Rephrase the input.

                This field is a member of `oneof`_ ``_block_reason``.
            safety_ratings (MutableSequence[google.ai.generativelanguage_v1alpha.types.SafetyRating]):
                Ratings for safety of the input.
                There is at most one rating per category.
        """

        class BlockReason(proto.Enum):
            r"""Specifies what was the reason why input was blocked.

            Values:
                BLOCK_REASON_UNSPECIFIED (0):
                    Default value. This value is unused.
                SAFETY (1):
                    Input was blocked due to safety reasons. Inspect
                    ``safety_ratings`` to understand which safety category
                    blocked it.
                OTHER (2):
                    Input was blocked due to other reasons.
            """
            BLOCK_REASON_UNSPECIFIED = 0
            SAFETY = 1
            OTHER = 2

        block_reason: "GenerateAnswerResponse.InputFeedback.BlockReason" = proto.Field(
            proto.ENUM,
            number=1,
            optional=True,
            enum="GenerateAnswerResponse.InputFeedback.BlockReason",
        )
        safety_ratings: MutableSequence[safety.SafetyRating] = proto.RepeatedField(
            proto.MESSAGE,
            number=2,
            message=safety.SafetyRating,
        )

    answer: "Candidate" = proto.Field(
        proto.MESSAGE,
        number=1,
        message="Candidate",
    )
    answerable_probability: float = proto.Field(
        proto.FLOAT,
        number=2,
        optional=True,
    )
    input_feedback: InputFeedback = proto.Field(
        proto.MESSAGE,
        number=3,
        optional=True,
        message=InputFeedback,
    )


class EmbedContentRequest(proto.Message):
    r"""Request containing the ``Content`` for the model to embed.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        model (str):
            Required. The model's resource name. This serves as an ID
            for the Model to use.

            This name should match a model name returned by the
            ``ListModels`` method.

            Format: ``models/{model}``
        content (google.ai.generativelanguage_v1alpha.types.Content):
            Required. The content to embed. Only the ``parts.text``
            fields will be counted.
        task_type (google.ai.generativelanguage_v1alpha.types.TaskType):
            Optional. Optional task type for which the embeddings will
            be used. Can only be set for ``models/embedding-001``.

            This field is a member of `oneof`_ ``_task_type``.
        title (str):
            Optional. An optional title for the text. Only applicable
            when TaskType is ``RETRIEVAL_DOCUMENT``.

            Note: Specifying a ``title`` for ``RETRIEVAL_DOCUMENT``
            provides better quality embeddings for retrieval.

            This field is a member of `oneof`_ ``_title``.
        output_dimensionality (int):
            Optional. Optional reduced dimension for the output
            embedding. If set, excessive values in the output embedding
            are truncated from the end. Supported by newer models since
            2024 only. You cannot set this value if using the earlier
            model (``models/embedding-001``).

            This field is a member of `oneof`_ ``_output_dimensionality``.
    """

    model: str = proto.Field(
        proto.STRING,
        number=1,
    )
    content: gag_content.Content = proto.Field(
        proto.MESSAGE,
        number=2,
        message=gag_content.Content,
    )
    task_type: "TaskType" = proto.Field(
        proto.ENUM,
        number=3,
        optional=True,
        enum="TaskType",
    )
    title: str = proto.Field(
        proto.STRING,
        number=4,
        optional=True,
    )
    output_dimensionality: int = proto.Field(
        proto.INT32,
        number=5,
        optional=True,
    )


class ContentEmbedding(proto.Message):
    r"""A list of floats representing an embedding.

    Attributes:
        values (MutableSequence[float]):
            The embedding values.
    """

    values: MutableSequence[float] = proto.RepeatedField(
        proto.FLOAT,
        number=1,
    )


class EmbedContentResponse(proto.Message):
    r"""The response to an ``EmbedContentRequest``.

    Attributes:
        embedding (google.ai.generativelanguage_v1alpha.types.ContentEmbedding):
            Output only. The embedding generated from the
            input content.
    """

    embedding: "ContentEmbedding" = proto.Field(
        proto.MESSAGE,
        number=1,
        message="ContentEmbedding",
    )


class BatchEmbedContentsRequest(proto.Message):
    r"""Batch request to get embeddings from the model for a list of
    prompts.

    Attributes:
        model (str):
            Required. The model's resource name. This serves as an ID
            for the Model to use.

            This name should match a model name returned by the
            ``ListModels`` method.

            Format: ``models/{model}``
        requests (MutableSequence[google.ai.generativelanguage_v1alpha.types.EmbedContentRequest]):
            Required. Embed requests for the batch. The model in each of
            these requests must match the model specified
            ``BatchEmbedContentsRequest.model``.
    """

    model: str = proto.Field(
        proto.STRING,
        number=1,
    )
    requests: MutableSequence["EmbedContentRequest"] = proto.RepeatedField(
        proto.MESSAGE,
        number=2,
        message="EmbedContentRequest",
    )


class BatchEmbedContentsResponse(proto.Message):
    r"""The response to a ``BatchEmbedContentsRequest``.

    Attributes:
        embeddings (MutableSequence[google.ai.generativelanguage_v1alpha.types.ContentEmbedding]):
            Output only. The embeddings for each request,
            in the same order as provided in the batch
            request.
    """

    embeddings: MutableSequence["ContentEmbedding"] = proto.RepeatedField(
        proto.MESSAGE,
        number=1,
        message="ContentEmbedding",
    )


class CountTokensRequest(proto.Message):
    r"""Counts the number of tokens in the ``prompt`` sent to a model.

    Models may tokenize text differently, so each model may return a
    different ``token_count``.

    Attributes:
        model (str):
            Required. The model's resource name. This serves as an ID
            for the Model to use.

            This name should match a model name returned by the
            ``ListModels`` method.

            Format: ``models/{model}``
        contents (MutableSequence[google.ai.generativelanguage_v1alpha.types.Content]):
            Optional. The input given to the model as a prompt. This
            field is ignored when ``generate_content_request`` is set.
        generate_content_request (google.ai.generativelanguage_v1alpha.types.GenerateContentRequest):
            Optional. The overall input given to the ``Model``. This
            includes the prompt as well as other model steering
            information like `system
            instructions <https://ai.google.dev/gemini-api/docs/system-instructions>`__,
            and/or function declarations for `function
            calling <https://ai.google.dev/gemini-api/docs/function-calling>`__.
            ``Model``\ s/\ ``Content``\ s and
            ``generate_content_request``\ s are mutually exclusive. You
            can either send ``Model`` + ``Content``\ s or a
            ``generate_content_request``, but never both.
    """

    model: str = proto.Field(
        proto.STRING,
        number=1,
    )
    contents: MutableSequence[gag_content.Content] = proto.RepeatedField(
        proto.MESSAGE,
        number=2,
        message=gag_content.Content,
    )
    generate_content_request: "GenerateContentRequest" = proto.Field(
        proto.MESSAGE,
        number=3,
        message="GenerateContentRequest",
    )


class CountTokensResponse(proto.Message):
    r"""A response from ``CountTokens``.

    It returns the model's ``token_count`` for the ``prompt``.

    Attributes:
        total_tokens (int):
            The number of tokens that the ``Model`` tokenizes the
            ``prompt`` into. Always non-negative.
        cached_content_token_count (int):
            Number of tokens in the cached part of the
            prompt (the cached content).
    """

    total_tokens: int = proto.Field(
        proto.INT32,
        number=1,
    )
    cached_content_token_count: int = proto.Field(
        proto.INT32,
        number=5,
    )


class BidiGenerateContentSetup(proto.Message):
    r"""Message to be sent in the first and only first
    ``BidiGenerateContentClientMessage``. Contains configuration that
    will apply for the duration of the streaming RPC.

    Clients should wait for a ``BidiGenerateContentSetupComplete``
    message before sending any additional messages.

    Attributes:
        model (str):
            Required. The model's resource name. This serves as an ID
            for the Model to use.

            Format: ``models/{model}``
        generation_config (google.ai.generativelanguage_v1alpha.types.GenerationConfig):
            Optional. Generation config.

            The following fields are not supported:

            -  ``response_logprobs``
            -  ``response_mime_type``
            -  ``logprobs``
            -  ``response_schema``
            -  ``stop_sequence``
            -  ``routing_config``
            -  ``audio_timestamp``
        system_instruction (google.ai.generativelanguage_v1alpha.types.Content):
            Optional. The user provided system
            instructions for the model.
            Note: Only text should be used in parts and
            content in each part will be in a separate
            paragraph.
        tools (MutableSequence[google.ai.generativelanguage_v1alpha.types.Tool]):
            Optional. A list of ``Tools`` the model may use to generate
            the next response.

            A ``Tool`` is a piece of code that enables the system to
            interact with external systems to perform an action, or set
            of actions, outside of knowledge and scope of the model.
    """

    model: str = proto.Field(
        proto.STRING,
        number=1,
    )
    generation_config: "GenerationConfig" = proto.Field(
        proto.MESSAGE,
        number=2,
        message="GenerationConfig",
    )
    system_instruction: gag_content.Content = proto.Field(
        proto.MESSAGE,
        number=3,
        message=gag_content.Content,
    )
    tools: MutableSequence[gag_content.Tool] = proto.RepeatedField(
        proto.MESSAGE,
        number=4,
        message=gag_content.Tool,
    )


class BidiGenerateContentClientContent(proto.Message):
    r"""Incremental update of the current conversation delivered from
    the client. All of the content here is unconditionally appended
    to the conversation history and used as part of the prompt to
    the model to generate content.

    A message here will interrupt any current model generation.

    Attributes:
        turns (MutableSequence[google.ai.generativelanguage_v1alpha.types.Content]):
            Optional. The content appended to the current
            conversation with the model.
            For single-turn queries, this is a single
            instance. For multi-turn queries, this is a
            repeated field that contains conversation
            history and the latest request.
        turn_complete (bool):
            Optional. If true, indicates that the server
            content generation should start with the
            currently accumulated prompt. Otherwise, the
            server awaits additional messages before
            starting generation.
    """

    turns: MutableSequence[gag_content.Content] = proto.RepeatedField(
        proto.MESSAGE,
        number=1,
        message=gag_content.Content,
    )
    turn_complete: bool = proto.Field(
        proto.BOOL,
        number=2,
    )


class BidiGenerateContentRealtimeInput(proto.Message):
    r"""User input that is sent in real time.

    This is different from
    [BidiGenerateContentClientContent][google.ai.generativelanguage.v1alpha.BidiGenerateContentClientContent]
    in a few ways:

    -  Can be sent continuously without interruption to model
       generation.
    -  If there is a need to mix data interleaved across the
       [BidiGenerateContentClientContent][google.ai.generativelanguage.v1alpha.BidiGenerateContentClientContent]
       and the
       [BidiGenerateContentRealtimeInput][google.ai.generativelanguage.v1alpha.BidiGenerateContentRealtimeInput],
       the server attempts to optimize for best response, but there are
       no guarantees.
    -  End of turn is not explicitly specified, but is rather derived
       from user activity (for example, end of speech).
    -  Even before the end of turn, the data is processed incrementally
       to optimize for a fast start of the response from the model.
    -  Is always direct user input that is sent in real time. Can be
       sent continuously without interruptions. The model automatically
       detects the beginning and the end of user speech and starts or
       terminates streaming the response accordingly. Data is processed
       incrementally as it arrives, minimizing latency.

    Attributes:
        media_chunks (MutableSequence[google.ai.generativelanguage_v1alpha.types.Blob]):
            Optional. Inlined bytes data for media input.
    """

    media_chunks: MutableSequence[gag_content.Blob] = proto.RepeatedField(
        proto.MESSAGE,
        number=1,
        message=gag_content.Blob,
    )


class BidiGenerateContentToolResponse(proto.Message):
    r"""Client generated response to a ``ToolCall`` received from the
    server. Individual ``FunctionResponse`` objects are matched to the
    respective ``FunctionCall`` objects by the ``id`` field.

    Note that in the unary and server-streaming GenerateContent APIs
    function calling happens by exchanging the ``Content`` parts, while
    in the bidi GenerateContent APIs function calling happens over these
    dedicated set of messages.

    Attributes:
        function_responses (MutableSequence[google.ai.generativelanguage_v1alpha.types.FunctionResponse]):
            Optional. The response to the function calls.
    """

    function_responses: MutableSequence[
        gag_content.FunctionResponse
    ] = proto.RepeatedField(
        proto.MESSAGE,
        number=1,
        message=gag_content.FunctionResponse,
    )


class BidiGenerateContentClientMessage(proto.Message):
    r"""Messages sent by the client in the BidiGenerateContent call.

    This message has `oneof`_ fields (mutually exclusive fields).
    For each oneof, at most one member field can be set at the same time.
    Setting any member of the oneof automatically clears all other
    members.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        setup (google.ai.generativelanguage_v1alpha.types.BidiGenerateContentSetup):
            Optional. Session configuration sent in the
            first and only first client message.

            This field is a member of `oneof`_ ``message_type``.
        client_content (google.ai.generativelanguage_v1alpha.types.BidiGenerateContentClientContent):
            Optional. Incremental update of the current
            conversation delivered from the client.

            This field is a member of `oneof`_ ``message_type``.
        realtime_input (google.ai.generativelanguage_v1alpha.types.BidiGenerateContentRealtimeInput):
            Optional. User input that is sent in real
            time.

            This field is a member of `oneof`_ ``message_type``.
        tool_response (google.ai.generativelanguage_v1alpha.types.BidiGenerateContentToolResponse):
            Optional. Response to a ``ToolCallMessage`` received from
            the server.

            This field is a member of `oneof`_ ``message_type``.
    """

    setup: "BidiGenerateContentSetup" = proto.Field(
        proto.MESSAGE,
        number=1,
        oneof="message_type",
        message="BidiGenerateContentSetup",
    )
    client_content: "BidiGenerateContentClientContent" = proto.Field(
        proto.MESSAGE,
        number=2,
        oneof="message_type",
        message="BidiGenerateContentClientContent",
    )
    realtime_input: "BidiGenerateContentRealtimeInput" = proto.Field(
        proto.MESSAGE,
        number=3,
        oneof="message_type",
        message="BidiGenerateContentRealtimeInput",
    )
    tool_response: "BidiGenerateContentToolResponse" = proto.Field(
        proto.MESSAGE,
        number=4,
        oneof="message_type",
        message="BidiGenerateContentToolResponse",
    )


class BidiGenerateContentSetupComplete(proto.Message):
    r"""Sent in response to a ``BidiGenerateContentSetup`` message from the
    client.

    """


class BidiGenerateContentServerContent(proto.Message):
    r"""Incremental server update generated by the model in response
    to client messages.

    Content is generated as quickly as possible, and not in real
    time. Clients may choose to buffer and play it out in real time.


    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        model_turn (google.ai.generativelanguage_v1alpha.types.Content):
            Output only. The content that the model has
            generated as part of the current conversation
            with the user.

            This field is a member of `oneof`_ ``_model_turn``.
        turn_complete (bool):
            Output only. If true, indicates that the model is done
            generating. Generation will only start in response to
            additional client messages. Can be set alongside
            ``content``, indicating that the ``content`` is the last in
            the turn.
        interrupted (bool):
            Output only. If true, indicates that a client
            message has interrupted current model
            generation. If the client is playing out the
            content in real time, this is a good signal to
            stop and empty the current playback queue.
        grounding_metadata (google.ai.generativelanguage_v1alpha.types.GroundingMetadata):
            Output only. Grounding metadata for the
            generated content.
    """

    model_turn: gag_content.Content = proto.Field(
        proto.MESSAGE,
        number=1,
        optional=True,
        message=gag_content.Content,
    )
    turn_complete: bool = proto.Field(
        proto.BOOL,
        number=2,
    )
    interrupted: bool = proto.Field(
        proto.BOOL,
        number=3,
    )
    grounding_metadata: "GroundingMetadata" = proto.Field(
        proto.MESSAGE,
        number=4,
        message="GroundingMetadata",
    )


class BidiGenerateContentToolCall(proto.Message):
    r"""Request for the client to execute the ``function_calls`` and return
    the responses with the matching ``id``\ s.

    Attributes:
        function_calls (MutableSequence[google.ai.generativelanguage_v1alpha.types.FunctionCall]):
            Output only. The function call to be
            executed.
    """

    function_calls: MutableSequence[gag_content.FunctionCall] = proto.RepeatedField(
        proto.MESSAGE,
        number=2,
        message=gag_content.FunctionCall,
    )


class BidiGenerateContentToolCallCancellation(proto.Message):
    r"""Notification for the client that a previously issued
    ``ToolCallMessage`` with the specified ``id``\ s should have been
    not executed and should be cancelled. If there were side-effects to
    those tool calls, clients may attempt to undo the tool calls. This
    message occurs only in cases where the clients interrupt server
    turns.

    Attributes:
        ids (MutableSequence[str]):
            Output only. The ids of the tool calls to be
            cancelled.
    """

    ids: MutableSequence[str] = proto.RepeatedField(
        proto.STRING,
        number=1,
    )


class BidiGenerateContentServerMessage(proto.Message):
    r"""Response message for the BidiGenerateContent call.

    This message has `oneof`_ fields (mutually exclusive fields).
    For each oneof, at most one member field can be set at the same time.
    Setting any member of the oneof automatically clears all other
    members.

    .. _oneof: https://proto-plus-python.readthedocs.io/en/stable/fields.html#oneofs-mutually-exclusive-fields

    Attributes:
        setup_complete (google.ai.generativelanguage_v1alpha.types.BidiGenerateContentSetupComplete):
            Output only. Sent in response to a
            ``BidiGenerateContentSetup`` message from the client when
            setup is complete.

            This field is a member of `oneof`_ ``message_type``.
        server_content (google.ai.generativelanguage_v1alpha.types.BidiGenerateContentServerContent):
            Output only. Content generated by the model
            in response to client messages.

            This field is a member of `oneof`_ ``message_type``.
        tool_call (google.ai.generativelanguage_v1alpha.types.BidiGenerateContentToolCall):
            Output only. Request for the client to execute the
            ``function_calls`` and return the responses with the
            matching ``id``\ s.

            This field is a member of `oneof`_ ``message_type``.
        tool_call_cancellation (google.ai.generativelanguage_v1alpha.types.BidiGenerateContentToolCallCancellation):
            Output only. Notification for the client that a previously
            issued ``ToolCallMessage`` with the specified ``id``\ s
            should be cancelled.

            This field is a member of `oneof`_ ``message_type``.
    """

    setup_complete: "BidiGenerateContentSetupComplete" = proto.Field(
        proto.MESSAGE,
        number=2,
        oneof="message_type",
        message="BidiGenerateContentSetupComplete",
    )
    server_content: "BidiGenerateContentServerContent" = proto.Field(
        proto.MESSAGE,
        number=3,
        oneof="message_type",
        message="BidiGenerateContentServerContent",
    )
    tool_call: "BidiGenerateContentToolCall" = proto.Field(
        proto.MESSAGE,
        number=4,
        oneof="message_type",
        message="BidiGenerateContentToolCall",
    )
    tool_call_cancellation: "BidiGenerateContentToolCallCancellation" = proto.Field(
        proto.MESSAGE,
        number=5,
        oneof="message_type",
        message="BidiGenerateContentToolCallCancellation",
    )


__all__ = tuple(sorted(__protobuf__.manifest))
