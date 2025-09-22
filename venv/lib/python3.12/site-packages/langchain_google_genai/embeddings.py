import re
import string
from typing import Any, Dict, List, Optional

# TODO: remove ignore once the google package is published with types
from google.ai.generativelanguage_v1beta.types import (
    BatchEmbedContentsRequest,
    EmbedContentRequest,
    EmbedContentResponse,
)
from langchain_core.embeddings import Embeddings
from langchain_core.utils import secret_from_env
from pydantic import BaseModel, Field, SecretStr, model_validator
from typing_extensions import Self

from langchain_google_genai._common import (
    GoogleGenerativeAIError,
    get_client_info,
)
from langchain_google_genai._genai_extension import (
    build_generative_async_service,
    build_generative_service,
)

_MAX_TOKENS_PER_BATCH = 20000
_DEFAULT_BATCH_SIZE = 100


class GoogleGenerativeAIEmbeddings(BaseModel, Embeddings):
    """`Google Generative AI Embeddings`.

    To use, you must have either:

        1. The ``GOOGLE_API_KEY`` environment variable set with your API key, or
        2. Pass your API key using the google_api_key kwarg to the
        GoogleGenerativeAIEmbeddings constructor.

    Example:
        .. code-block:: python

            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
            embeddings.embed_query("What's our Q1 revenue?")
    """

    client: Any = None  #: :meta private:
    async_client: Any = None  #: :meta private:
    model: str = Field(
        ...,
        description="The name of the embedding model to use. "
        "Example: ``'models/embedding-001'``",
    )
    task_type: Optional[str] = Field(
        default=None,
        description="The task type. Valid options include: "
        "``'task_type_unspecified'``, ``'retrieval_query'``, ``'retrieval_document'``, "
        "``'semantic_similarity'``, ``'classification'``, and ``'clustering'``",
    )
    google_api_key: Optional[SecretStr] = Field(
        default_factory=secret_from_env("GOOGLE_API_KEY", default=None),
        description=(
            "The Google API key to use. If not provided, "
            "the GOOGLE_API_KEY environment variable will be used."
        ),
    )
    credentials: Any = Field(
        default=None,
        exclude=True,
        description="The default custom credentials "
        "(google.auth.credentials.Credentials) to use when making API calls. If not "
        "provided, credentials will be ascertained from the GOOGLE_API_KEY envvar",
    )
    client_options: Optional[Dict] = Field(
        default=None,
        description=(
            "A dictionary of client options to pass to the Google API client, "
            "such as `api_endpoint`."
        ),
    )
    transport: Optional[str] = Field(
        default=None,
        description="A string, one of: [``'rest'``, ``'grpc'``, ``'grpc_asyncio'``].",
    )
    request_options: Optional[Dict] = Field(
        default=None,
        description="A dictionary of request options to pass to the Google API client."
        "Example: `{'timeout': 10}`",
    )

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        """Validates params and passes them to google-generativeai package."""
        if isinstance(self.google_api_key, SecretStr):
            google_api_key: Optional[str] = self.google_api_key.get_secret_value()
        else:
            google_api_key = self.google_api_key
        client_info = get_client_info("GoogleGenerativeAIEmbeddings")

        if not any(self.model.startswith(prefix) for prefix in ("models/",)):
            self.model = f"models/{self.model}"

        self.client = build_generative_service(
            credentials=self.credentials,
            api_key=google_api_key,
            client_info=client_info,
            client_options=self.client_options,
            transport=self.transport,
        )
        self.async_client = build_generative_async_service(
            credentials=self.credentials,
            api_key=google_api_key,
            client_info=client_info,
            client_options=self.client_options,
            transport=self.transport,
        )
        return self

    @staticmethod
    def _split_by_punctuation(text: str) -> List[str]:
        """Splits a string by punctuation and whitespace characters."""
        split_by = string.punctuation + "\t\n "
        pattern = f"([{split_by}])"
        # Using re.split to split the text based on the pattern
        return [segment for segment in re.split(pattern, text) if segment]

    @staticmethod
    def _prepare_batches(texts: List[str], batch_size: int) -> List[List[str]]:
        """Splits texts in batches based on current maximum batch size
        and maximum tokens per request.
        """
        text_index = 0
        texts_len = len(texts)
        batch_token_len = 0
        batches: List[List[str]] = []
        current_batch: List[str] = []
        if texts_len == 0:
            return []
        while text_index < texts_len:
            current_text = texts[text_index]
            # Number of tokens per a text is conservatively estimated
            # as 2 times number of words, punctuation and whitespace characters.
            # Using `count_tokens` API will make batching too expensive.
            # Utilizing a tokenizer, would add a dependency that would not
            # necessarily be reused by the application using this class.
            current_text_token_cnt = (
                len(GoogleGenerativeAIEmbeddings._split_by_punctuation(current_text))
                * 2
            )
            end_of_batch = False
            if current_text_token_cnt > _MAX_TOKENS_PER_BATCH:
                # Current text is too big even for a single batch.
                # Such request will fail, but we still make a batch
                # so that the app can get the error from the API.
                if len(current_batch) > 0:
                    # Adding current batch if not empty.
                    batches.append(current_batch)
                current_batch = [current_text]
                text_index += 1
                end_of_batch = True
            elif (
                batch_token_len + current_text_token_cnt > _MAX_TOKENS_PER_BATCH
                or len(current_batch) == batch_size
            ):
                end_of_batch = True
            else:
                if text_index == texts_len - 1:
                    # Last element - even though the batch may be not big,
                    # we still need to make it.
                    end_of_batch = True
                batch_token_len += current_text_token_cnt
                current_batch.append(current_text)
                text_index += 1
            if end_of_batch:
                batches.append(current_batch)
                current_batch = []
                batch_token_len = 0
        return batches

    def _prepare_request(
        self,
        text: str,
        *,
        task_type: Optional[str] = None,
        title: Optional[str] = None,
        output_dimensionality: Optional[int] = None,
    ) -> EmbedContentRequest:
        task_type = self.task_type or task_type or "RETRIEVAL_DOCUMENT"
        request = EmbedContentRequest(
            content={"parts": [{"text": text}]},
            model=self.model,
            task_type=task_type.upper(),
            title=title,
            output_dimensionality=output_dimensionality,
        )
        return request

    def embed_documents(
        self,
        texts: List[str],
        *,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        task_type: Optional[str] = None,
        titles: Optional[List[str]] = None,
        output_dimensionality: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed a list of strings using the `batch endpoint <https://ai.google.dev/api/embeddings#method:-models.batchembedcontents>`__.

        Google Generative AI currently sets a max batch size of 100 strings.

        Args:
            texts: List[str] The list of strings to embed.
            batch_size: [int] The batch size of embeddings to send to the model
            task_type: `task_type <https://ai.google.dev/api/embeddings#tasktype>`__
            titles: An optional list of titles for texts provided.
              Only applicable when TaskType is ``'RETRIEVAL_DOCUMENT'``.
            output_dimensionality: Optional `reduced dimension for the output embedding <https://ai.google.dev/api/embeddings#EmbedContentRequest>`__.
        Returns:
            List of embeddings, one for each text.
        """
        embeddings: List[List[float]] = []
        batch_start_index = 0
        for batch in GoogleGenerativeAIEmbeddings._prepare_batches(texts, batch_size):
            if titles:
                titles_batch = titles[
                    batch_start_index : batch_start_index + len(batch)
                ]
                batch_start_index += len(batch)
            else:
                titles_batch = [None] * len(batch)  # type: ignore[list-item]

            requests = [
                self._prepare_request(
                    text=text,
                    task_type=task_type,
                    title=title,
                    output_dimensionality=output_dimensionality,
                )
                for text, title in zip(batch, titles_batch)
            ]

            try:
                result = self.client.batch_embed_contents(
                    BatchEmbedContentsRequest(requests=requests, model=self.model)
                )
            except Exception as e:
                raise GoogleGenerativeAIError(f"Error embedding content: {e}") from e
            embeddings.extend([list(e.values) for e in result.embeddings])
        return embeddings

    def embed_query(
        self,
        text: str,
        *,
        task_type: Optional[str] = None,
        title: Optional[str] = None,
        output_dimensionality: Optional[int] = None,
    ) -> List[float]:
        """Embed a text, using the `non-batch endpoint <https://ai.google.dev/api/embeddings#method:-models.embedcontent>`__.

        Args:
            text: The text to embed.
            task_type: `task_type <https://ai.google.dev/api/embeddings#tasktype>`__
            title: An optional title for the text.
              Only applicable when TaskType is ``'RETRIEVAL_DOCUMENT'``.
            output_dimensionality: Optional `reduced dimension for the output embedding <https://ai.google.dev/api/embeddings#EmbedContentRequest>`__.

        Returns:
            Embedding for the text.
        """
        task_type_to_use = task_type if task_type else self.task_type
        if task_type_to_use is None:
            task_type_to_use = "RETRIEVAL_QUERY"
        try:
            request: EmbedContentRequest = self._prepare_request(
                text=text,
                task_type=task_type,
                title=title,
                output_dimensionality=output_dimensionality,
            )
            result: EmbedContentResponse = self.client.embed_content(request)
        except Exception as e:
            raise GoogleGenerativeAIError(f"Error embedding content: {e}") from e
        return list(result.embedding.values)

    async def aembed_documents(
        self,
        texts: List[str],
        *,
        batch_size: int = _DEFAULT_BATCH_SIZE,
        task_type: Optional[str] = None,
        titles: Optional[List[str]] = None,
        output_dimensionality: Optional[int] = None,
    ) -> List[List[float]]:
        """Embed a list of strings using the `batch endpoint <https://ai.google.dev/api/embeddings#method:-models.batchembedcontents>`__.

        Google Generative AI currently sets a max batch size of 100 strings.

        Args:
            texts: List[str] The list of strings to embed.
            batch_size: [int] The batch size of embeddings to send to the model
            task_type: `task_type <https://ai.google.dev/api/embeddings#tasktype>`__
            titles: An optional list of titles for texts provided.
                Only applicable when TaskType is ``'RETRIEVAL_DOCUMENT'``.
            output_dimensionality: Optional `reduced dimension for the output embedding <https://ai.google.dev/api/embeddings#EmbedContentRequest>`__.
        Returns:
            List of embeddings, one for each text.
        """
        embeddings: List[List[float]] = []
        batch_start_index = 0
        for batch in GoogleGenerativeAIEmbeddings._prepare_batches(texts, batch_size):
            if titles:
                titles_batch = titles[
                    batch_start_index : batch_start_index + len(batch)
                ]
                batch_start_index += len(batch)
            else:
                titles_batch = [None] * len(batch)  # type: ignore[list-item]

            requests = [
                self._prepare_request(
                    text=text,
                    task_type=task_type,
                    title=title,
                    output_dimensionality=output_dimensionality,
                )
                for text, title in zip(batch, titles_batch)
            ]

            try:
                result = await self.async_client.batch_embed_contents(
                    BatchEmbedContentsRequest(requests=requests, model=self.model)
                )
            except Exception as e:
                raise GoogleGenerativeAIError(f"Error embedding content: {e}") from e
            embeddings.extend([list(e.values) for e in result.embeddings])
        return embeddings

    async def aembed_query(
        self,
        text: str,
        *,
        task_type: Optional[str] = None,
        title: Optional[str] = None,
        output_dimensionality: Optional[int] = None,
    ) -> List[float]:
        """Embed a text, using the `non-batch endpoint <https://ai.google.dev/api/embeddings#method:-models.embedcontent>`__.

        Args:
            text: The text to embed.
            task_type: `task_type <https://ai.google.dev/api/embeddings#tasktype>`__
            title: An optional title for the text.
                Only applicable when TaskType is ``'RETRIEVAL_DOCUMENT'``.
            output_dimensionality: Optional `reduced dimension for the output embedding <https://ai.google.dev/api/embeddings#EmbedContentRequest>`__.

        Returns:
            Embedding for the text.
        """
        task_type_to_use = task_type if task_type else self.task_type
        if task_type_to_use is None:
            task_type_to_use = "RETRIEVAL_QUERY"
        try:
            request: EmbedContentRequest = self._prepare_request(
                text=text,
                task_type=task_type,
                title=title,
                output_dimensionality=output_dimensionality,
            )
            result: EmbedContentResponse = await self.async_client.embed_content(
                request
            )
        except Exception as e:
            raise GoogleGenerativeAIError(f"Error embedding content: {e}") from e
        return list(result.embedding.values)
