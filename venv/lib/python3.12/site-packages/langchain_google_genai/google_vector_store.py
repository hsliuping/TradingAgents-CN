"""Google Generative AI Vector Store.

The GenAI Semantic Retriever API is a managed end-to-end service that allows
developers to create a corpus of documents to perform semantic search on
related passages given a user query. For more information visit:
https://developers.generativeai.google/guide
"""

import asyncio
from functools import partial
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
)

import google.ai.generativelanguage as genai
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough
from langchain_core.vectorstores import VectorStore
from pydantic import BaseModel, PrivateAttr

from . import _genai_extension as genaix
from .genai_aqa import (
    AqaInput,
    AqaOutput,
    GenAIAqa,
)


class ServerSideEmbedding(Embeddings):
    """Do nothing embedding model where the embedding is done by the server."""

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[] for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return []


class DoesNotExistsException(Exception):
    def __init__(self, *, corpus_id: str, document_id: Optional[str] = None) -> None:
        if document_id is None:
            message = f"No such corpus {corpus_id}"
        else:
            message = f"No such document {document_id} under corpus {corpus_id}"
        super().__init__(message)


class _SemanticRetriever(BaseModel):
    """Wrapper class to Google's internal semantric retriever service."""

    name: genaix.EntityName
    _client: genai.RetrieverServiceClient = PrivateAttr()

    def __init__(self, *, client: genai.RetrieverServiceClient, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._client = client

    @classmethod
    def from_ids(
        cls, corpus_id: str, document_id: Optional[str]
    ) -> "_SemanticRetriever":
        name = genaix.EntityName(corpus_id=corpus_id, document_id=document_id)
        client = genaix.build_semantic_retriever()

        # Check the entity exists on Google server.
        if name.is_corpus():
            if genaix.get_corpus(corpus_id=corpus_id, client=client) is None:
                raise DoesNotExistsException(corpus_id=corpus_id)
        elif name.is_document():
            assert document_id is not None
            if (
                genaix.get_document(
                    corpus_id=corpus_id, document_id=document_id, client=client
                )
                is None
            ):
                raise DoesNotExistsException(
                    corpus_id=corpus_id, document_id=document_id
                )

        return cls(name=name, client=client)

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        document_id: Optional[str] = None,
    ) -> List[str]:
        if self.name.document_id is None and document_id is None:
            raise NotImplementedError(
                "Adding texts to a corpus directly is not supported. "
                "Please provide a document ID under the corpus first. "
                "Then add the texts to the document."
            )
        if (
            self.name.document_id is not None
            and document_id is not None
            and self.name.document_id != document_id
        ):
            raise NotImplementedError(
                f"Parameter `document_id` {document_id} does not match the "
                f"vector store's `document_id` {self.name.document_id}"
            )
        assert self.name.document_id or document_id is not None
        new_document_id = self.name.document_id or document_id or ""

        texts = list(texts)
        if metadatas is None:
            metadatas = [{} for _ in texts]
        if len(texts) != len(metadatas):
            raise ValueError(
                f"metadatas's length {len(metadatas)} and "
                f"texts's length {len(texts)} are mismatched"
            )

        chunks = genaix.batch_create_chunk(
            corpus_id=self.name.corpus_id,
            document_id=new_document_id,
            texts=texts,
            metadatas=metadatas,
            client=self._client,
        )

        return [chunk.name for chunk in chunks if chunk.name]

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float]]:
        if self.name.is_corpus():
            relevant_chunks = genaix.query_corpus(
                corpus_id=self.name.corpus_id,
                query=query,
                k=k,
                filter=filter,
                client=self._client,
            )
        else:
            assert self.name.is_document()
            assert self.name.document_id is not None
            relevant_chunks = genaix.query_document(
                corpus_id=self.name.corpus_id,
                document_id=self.name.document_id,
                query=query,
                k=k,
                filter=filter,
                client=self._client,
            )

        return [
            (chunk.chunk.data.string_value, chunk.chunk_relevance_score)
            for chunk in relevant_chunks
        ]

    def delete(self, ids: Optional[List[str]] = None, **kwargs: Any) -> Optional[bool]:
        for id in ids or []:
            name = genaix.EntityName.from_str(id)
            _delete_chunk(
                corpus_id=name.corpus_id,
                document_id=name.document_id,
                chunk_id=name.chunk_id,
                client=self._client,
            )
        return True


def _delete_chunk(
    *,
    corpus_id: str,
    document_id: Optional[str],
    chunk_id: Optional[str],
    client: genai.RetrieverServiceClient,
) -> None:
    if chunk_id is not None:
        if document_id is None:
            raise ValueError(f"Chunk {chunk_id} requires a document ID")
        genaix.delete_chunk(
            corpus_id=corpus_id,
            document_id=document_id,
            chunk_id=chunk_id,
            client=client,
        )
    elif document_id is not None:
        genaix.delete_document(
            corpus_id=corpus_id, document_id=document_id, client=client
        )
    else:
        genaix.delete_corpus(corpus_id=corpus_id, client=client)


class GoogleVectorStore(VectorStore):
    """Google GenerativeAI Vector Store.

    Currently, it computes the embedding vectors on the server side.

    Example: Add texts to an existing corpus.

        store = GoogleVectorStore(corpus_id="123")
        store.add_documents(documents, document_id="456")

    Example: Create a new corpus.

        store = GoogleVectorStore.create_corpus(
            corpus_id="123", display_name="My Google corpus")

    Example: Query the corpus for relevant passages.

        store.as_retriever() \
            .get_relevant_documents("Who caught the gingerbread man?")

    Example: Ask the corpus for grounded responses!

        aqa = store.as_aqa()
        response = aqa.invoke("Who caught the gingerbread man?")
        print(response.answer)
        print(response.attributed_passages)
        print(response.answerability_probability)

    You can also operate at Google's Document level.

    Example: Add texts to an existing Google Vector Store Document.

        doc_store = GoogleVectorStore(corpus_id="123", document_id="456")
        doc_store.add_documents(documents)

    Example: Create a new Google Vector Store Document.

        doc_store = GoogleVectorStore.create_document(
            corpus_id="123", document_id="456", display_name="My Google document")

    Example: Query the Google document.

        doc_store.as_retriever() \
            .get_relevant_documents("Who caught the gingerbread man?")

    For more details, see the class's methods.
    """

    _retriever: _SemanticRetriever

    def __init__(
        self, *, corpus_id: str, document_id: Optional[str] = None, **kwargs: Any
    ):
        """Returns an existing Google Semantic Retriever corpus or document.

        If just the corpus ID is provided, the vector store operates over all
        documents within that corpus.

        If the document ID is provided, the vector store operates over just that
        document.

        Raises:
            DoesNotExistsException if the IDs do not match to anything on Google
                server. In this case, consider using `create_corpus` or
                `create_document` to create one.
        """
        super().__init__(**kwargs)
        self._retriever = _SemanticRetriever.from_ids(corpus_id, document_id)

    @classmethod
    def create_corpus(
        cls,
        corpus_id: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> "GoogleVectorStore":
        """Create a Google Semantic Retriever corpus.

        Args:
            corpus_id: The ID to use to create the new corpus. If not provided,
                Google server will provide one.
            display_name: The title of the new corpus. If not provided, Google
                server will provide one.

        Returns:
            An instance of vector store that points to the newly created corpus.
        """
        client = genaix.build_semantic_retriever()
        corpus = genaix.create_corpus(
            corpus_id=corpus_id, display_name=display_name, client=client
        )

        n = genaix.EntityName.from_str(corpus.name)
        return cls(corpus_id=n.corpus_id)

    @classmethod
    def create_document(
        cls,
        corpus_id: str,
        document_id: Optional[str] = None,
        display_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "GoogleVectorStore":
        """Create a Google Semantic Retriever document.

        Args:
            corpus_id: ID of an existing corpus.
            document_id: The ID to use to create the new Google Semantic
                Retriever document. If not provided, Google server will provide
                one.
            display_name: The title of the new document. If not provided, Google
                server will provide one.

        Returns:
            An instance of vector store that points to the newly created
            document.
        """
        client = genaix.build_semantic_retriever()
        document = genaix.create_document(
            corpus_id=corpus_id,
            document_id=document_id,
            display_name=display_name,
            metadata=metadata,
            client=client,
        )

        assert document.name is not None
        d = genaix.EntityName.from_str(document.name)
        return cls(corpus_id=d.corpus_id, document_id=d.document_id)

    @classmethod
    def from_texts(
        cls,
        texts: List[str],
        embedding: Optional[Embeddings] = None,
        metadatas: Optional[List[dict[str, Any]]] = None,
        *,
        corpus_id: Optional[str] = None,  # str required
        document_id: Optional[str] = None,  # str required
        **kwargs: Any,
    ) -> "GoogleVectorStore":
        """Returns a vector store of an existing document with the specified text.

        Args:
            corpus_id: REQUIRED. Must be an existing corpus.
            document_id: REQUIRED. Must be an existing document.
            texts: Texts to be loaded into the vector store.

        Returns:
            A vector store pointing to the specified Google Semantic Retriever
            Document.

        Raises:
            DoesNotExistsException if the IDs do not match to anything at
                Google server.
        """
        if corpus_id is None or document_id is None:
            raise NotImplementedError(
                "Must provide an existing corpus ID and document ID"
            )

        doc_store = cls(corpus_id=corpus_id, document_id=document_id, **kwargs)
        doc_store.add_texts(texts, metadatas)

        return doc_store

    @property
    def name(self) -> str:
        """Returns the name of the Google entity.

        You shouldn't need to care about this unless you want to access your
        corpus or document via Google Generative AI API.
        """
        return str(self._retriever.name)

    @property
    def corpus_id(self) -> str:
        """Returns the corpus ID managed by this vector store."""
        return self._retriever.name.corpus_id

    @property
    def document_id(self) -> Optional[str]:
        """Returns the document ID managed by this vector store."""
        return self._retriever.name.document_id

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        *,
        document_id: Optional[str] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Add texts to the vector store.

        If the vector store points to a corpus (instead of a document), you must
        also provide a `document_id`.

        Returns:
            Chunk's names created on Google servers.
        """
        return self._retriever.add_texts(texts, metadatas, document_id)

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Search the vector store for relevant texts."""
        return [
            document
            for document, _ in self.similarity_search_with_score(
                query, k, filter, **kwargs
            )
        ]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Run similarity search with distance."""
        return [
            (Document(page_content=text), score)
            for text, score in self._retriever.similarity_search(query, k, filter)
        ]

    def delete(self, ids: Optional[List[str]] = None, **kwargs: Any) -> Optional[bool]:
        """Delete chunnks.

        Note that the "ids" are not corpus ID or document ID. Rather, these
        are the entity names returned by `add_texts`.

        Returns:
            True if successful. Otherwise, you should get an exception anyway.
        """
        return self._retriever.delete(ids)

    async def adelete(
        self, ids: Optional[List[str]] = None, **kwargs: Any
    ) -> Optional[bool]:
        return await asyncio.get_running_loop().run_in_executor(
            None, partial(self.delete, **kwargs), ids
        )

    def _select_relevance_score_fn(self) -> Callable[[float], float]:
        """
        TODO: Check with the team about this!
        The underlying vector store already returns a "score proper",
        i.e. one in [0, 1] where higher means more *similar*.
        """
        return lambda score: score

    def as_aqa(self, **kwargs: Any) -> Runnable[str, AqaOutput]:
        """Construct a Google Generative AI AQA engine.

        All arguments are optional.

        Args:
            answer_style: See
              `google.ai.generativelanguage.GenerateAnswerRequest.AnswerStyle`.
            safety_settings: See `google.ai.generativelanguage.SafetySetting`.
            temperature: 0.0 to 1.0.
        """
        return (
            RunnablePassthrough[str]()
            | {
                "prompt": RunnablePassthrough(),  # type: ignore[dict-item]
                "passages": self.as_retriever(),
            }
            | RunnableLambda(_toAqaInput)
            | GenAIAqa(**kwargs)
        )


def _toAqaInput(input: Dict[str, Any]) -> AqaInput:
    prompt = input["prompt"]
    assert isinstance(prompt, str)

    passages = input["passages"]
    assert isinstance(passages, list)

    source_passages: List[str] = []
    for passage in passages:
        assert isinstance(passage, Document)
        source_passages.append(passage.page_content)

    return AqaInput(
        prompt=prompt,
        source_passages=source_passages,
    )
