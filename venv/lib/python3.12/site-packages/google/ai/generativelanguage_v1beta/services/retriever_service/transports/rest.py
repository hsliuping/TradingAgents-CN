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
import dataclasses
import json  # type: ignore
import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
import warnings

from google.api_core import exceptions as core_exceptions
from google.api_core import gapic_v1, rest_helpers, rest_streaming
from google.api_core import retry as retries
from google.auth import credentials as ga_credentials  # type: ignore
from google.auth.transport.requests import AuthorizedSession  # type: ignore
from google.longrunning import operations_pb2  # type: ignore
from google.protobuf import empty_pb2  # type: ignore
from google.protobuf import json_format
from requests import __version__ as requests_version

from google.ai.generativelanguage_v1beta.types import retriever, retriever_service

from .base import DEFAULT_CLIENT_INFO as BASE_DEFAULT_CLIENT_INFO
from .rest_base import _BaseRetrieverServiceRestTransport

try:
    OptionalRetry = Union[retries.Retry, gapic_v1.method._MethodDefault, None]
except AttributeError:  # pragma: NO COVER
    OptionalRetry = Union[retries.Retry, object, None]  # type: ignore

try:
    from google.api_core import client_logging  # type: ignore

    CLIENT_LOGGING_SUPPORTED = True  # pragma: NO COVER
except ImportError:  # pragma: NO COVER
    CLIENT_LOGGING_SUPPORTED = False

_LOGGER = logging.getLogger(__name__)

DEFAULT_CLIENT_INFO = gapic_v1.client_info.ClientInfo(
    gapic_version=BASE_DEFAULT_CLIENT_INFO.gapic_version,
    grpc_version=None,
    rest_version=f"requests@{requests_version}",
)


class RetrieverServiceRestInterceptor:
    """Interceptor for RetrieverService.

    Interceptors are used to manipulate requests, request metadata, and responses
    in arbitrary ways.
    Example use cases include:
    * Logging
    * Verifying requests according to service or custom semantics
    * Stripping extraneous information from responses

    These use cases and more can be enabled by injecting an
    instance of a custom subclass when constructing the RetrieverServiceRestTransport.

    .. code-block:: python
        class MyCustomRetrieverServiceInterceptor(RetrieverServiceRestInterceptor):
            def pre_batch_create_chunks(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_batch_create_chunks(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_batch_delete_chunks(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def pre_batch_update_chunks(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_batch_update_chunks(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_create_chunk(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_create_chunk(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_create_corpus(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_create_corpus(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_create_document(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_create_document(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_delete_chunk(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def pre_delete_corpus(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def pre_delete_document(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def pre_get_chunk(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_get_chunk(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_get_corpus(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_get_corpus(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_get_document(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_get_document(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_list_chunks(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_list_chunks(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_list_corpora(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_list_corpora(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_list_documents(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_list_documents(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_query_corpus(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_query_corpus(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_query_document(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_query_document(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_update_chunk(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_update_chunk(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_update_corpus(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_update_corpus(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_update_document(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_update_document(self, response):
                logging.log(f"Received response: {response}")
                return response

        transport = RetrieverServiceRestTransport(interceptor=MyCustomRetrieverServiceInterceptor())
        client = RetrieverServiceClient(transport=transport)


    """

    def pre_batch_create_chunks(
        self,
        request: retriever_service.BatchCreateChunksRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.BatchCreateChunksRequest,
        Sequence[Tuple[str, Union[str, bytes]]],
    ]:
        """Pre-rpc interceptor for batch_create_chunks

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_batch_create_chunks(
        self, response: retriever_service.BatchCreateChunksResponse
    ) -> retriever_service.BatchCreateChunksResponse:
        """Post-rpc interceptor for batch_create_chunks

        DEPRECATED. Please use the `post_batch_create_chunks_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_batch_create_chunks` interceptor runs
        before the `post_batch_create_chunks_with_metadata` interceptor.
        """
        return response

    def post_batch_create_chunks_with_metadata(
        self,
        response: retriever_service.BatchCreateChunksResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.BatchCreateChunksResponse,
        Sequence[Tuple[str, Union[str, bytes]]],
    ]:
        """Post-rpc interceptor for batch_create_chunks

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_batch_create_chunks_with_metadata`
        interceptor in new development instead of the `post_batch_create_chunks` interceptor.
        When both interceptors are used, this `post_batch_create_chunks_with_metadata` interceptor runs after the
        `post_batch_create_chunks` interceptor. The (possibly modified) response returned by
        `post_batch_create_chunks` will be passed to
        `post_batch_create_chunks_with_metadata`.
        """
        return response, metadata

    def pre_batch_delete_chunks(
        self,
        request: retriever_service.BatchDeleteChunksRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.BatchDeleteChunksRequest,
        Sequence[Tuple[str, Union[str, bytes]]],
    ]:
        """Pre-rpc interceptor for batch_delete_chunks

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def pre_batch_update_chunks(
        self,
        request: retriever_service.BatchUpdateChunksRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.BatchUpdateChunksRequest,
        Sequence[Tuple[str, Union[str, bytes]]],
    ]:
        """Pre-rpc interceptor for batch_update_chunks

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_batch_update_chunks(
        self, response: retriever_service.BatchUpdateChunksResponse
    ) -> retriever_service.BatchUpdateChunksResponse:
        """Post-rpc interceptor for batch_update_chunks

        DEPRECATED. Please use the `post_batch_update_chunks_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_batch_update_chunks` interceptor runs
        before the `post_batch_update_chunks_with_metadata` interceptor.
        """
        return response

    def post_batch_update_chunks_with_metadata(
        self,
        response: retriever_service.BatchUpdateChunksResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.BatchUpdateChunksResponse,
        Sequence[Tuple[str, Union[str, bytes]]],
    ]:
        """Post-rpc interceptor for batch_update_chunks

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_batch_update_chunks_with_metadata`
        interceptor in new development instead of the `post_batch_update_chunks` interceptor.
        When both interceptors are used, this `post_batch_update_chunks_with_metadata` interceptor runs after the
        `post_batch_update_chunks` interceptor. The (possibly modified) response returned by
        `post_batch_update_chunks` will be passed to
        `post_batch_update_chunks_with_metadata`.
        """
        return response, metadata

    def pre_create_chunk(
        self,
        request: retriever_service.CreateChunkRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.CreateChunkRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for create_chunk

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_create_chunk(self, response: retriever.Chunk) -> retriever.Chunk:
        """Post-rpc interceptor for create_chunk

        DEPRECATED. Please use the `post_create_chunk_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_create_chunk` interceptor runs
        before the `post_create_chunk_with_metadata` interceptor.
        """
        return response

    def post_create_chunk_with_metadata(
        self,
        response: retriever.Chunk,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[retriever.Chunk, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for create_chunk

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_create_chunk_with_metadata`
        interceptor in new development instead of the `post_create_chunk` interceptor.
        When both interceptors are used, this `post_create_chunk_with_metadata` interceptor runs after the
        `post_create_chunk` interceptor. The (possibly modified) response returned by
        `post_create_chunk` will be passed to
        `post_create_chunk_with_metadata`.
        """
        return response, metadata

    def pre_create_corpus(
        self,
        request: retriever_service.CreateCorpusRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.CreateCorpusRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for create_corpus

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_create_corpus(self, response: retriever.Corpus) -> retriever.Corpus:
        """Post-rpc interceptor for create_corpus

        DEPRECATED. Please use the `post_create_corpus_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_create_corpus` interceptor runs
        before the `post_create_corpus_with_metadata` interceptor.
        """
        return response

    def post_create_corpus_with_metadata(
        self,
        response: retriever.Corpus,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[retriever.Corpus, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for create_corpus

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_create_corpus_with_metadata`
        interceptor in new development instead of the `post_create_corpus` interceptor.
        When both interceptors are used, this `post_create_corpus_with_metadata` interceptor runs after the
        `post_create_corpus` interceptor. The (possibly modified) response returned by
        `post_create_corpus` will be passed to
        `post_create_corpus_with_metadata`.
        """
        return response, metadata

    def pre_create_document(
        self,
        request: retriever_service.CreateDocumentRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.CreateDocumentRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for create_document

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_create_document(self, response: retriever.Document) -> retriever.Document:
        """Post-rpc interceptor for create_document

        DEPRECATED. Please use the `post_create_document_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_create_document` interceptor runs
        before the `post_create_document_with_metadata` interceptor.
        """
        return response

    def post_create_document_with_metadata(
        self,
        response: retriever.Document,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[retriever.Document, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for create_document

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_create_document_with_metadata`
        interceptor in new development instead of the `post_create_document` interceptor.
        When both interceptors are used, this `post_create_document_with_metadata` interceptor runs after the
        `post_create_document` interceptor. The (possibly modified) response returned by
        `post_create_document` will be passed to
        `post_create_document_with_metadata`.
        """
        return response, metadata

    def pre_delete_chunk(
        self,
        request: retriever_service.DeleteChunkRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.DeleteChunkRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for delete_chunk

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def pre_delete_corpus(
        self,
        request: retriever_service.DeleteCorpusRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.DeleteCorpusRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for delete_corpus

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def pre_delete_document(
        self,
        request: retriever_service.DeleteDocumentRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.DeleteDocumentRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for delete_document

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def pre_get_chunk(
        self,
        request: retriever_service.GetChunkRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.GetChunkRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for get_chunk

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_get_chunk(self, response: retriever.Chunk) -> retriever.Chunk:
        """Post-rpc interceptor for get_chunk

        DEPRECATED. Please use the `post_get_chunk_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_get_chunk` interceptor runs
        before the `post_get_chunk_with_metadata` interceptor.
        """
        return response

    def post_get_chunk_with_metadata(
        self,
        response: retriever.Chunk,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[retriever.Chunk, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for get_chunk

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_get_chunk_with_metadata`
        interceptor in new development instead of the `post_get_chunk` interceptor.
        When both interceptors are used, this `post_get_chunk_with_metadata` interceptor runs after the
        `post_get_chunk` interceptor. The (possibly modified) response returned by
        `post_get_chunk` will be passed to
        `post_get_chunk_with_metadata`.
        """
        return response, metadata

    def pre_get_corpus(
        self,
        request: retriever_service.GetCorpusRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.GetCorpusRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for get_corpus

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_get_corpus(self, response: retriever.Corpus) -> retriever.Corpus:
        """Post-rpc interceptor for get_corpus

        DEPRECATED. Please use the `post_get_corpus_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_get_corpus` interceptor runs
        before the `post_get_corpus_with_metadata` interceptor.
        """
        return response

    def post_get_corpus_with_metadata(
        self,
        response: retriever.Corpus,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[retriever.Corpus, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for get_corpus

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_get_corpus_with_metadata`
        interceptor in new development instead of the `post_get_corpus` interceptor.
        When both interceptors are used, this `post_get_corpus_with_metadata` interceptor runs after the
        `post_get_corpus` interceptor. The (possibly modified) response returned by
        `post_get_corpus` will be passed to
        `post_get_corpus_with_metadata`.
        """
        return response, metadata

    def pre_get_document(
        self,
        request: retriever_service.GetDocumentRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.GetDocumentRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for get_document

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_get_document(self, response: retriever.Document) -> retriever.Document:
        """Post-rpc interceptor for get_document

        DEPRECATED. Please use the `post_get_document_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_get_document` interceptor runs
        before the `post_get_document_with_metadata` interceptor.
        """
        return response

    def post_get_document_with_metadata(
        self,
        response: retriever.Document,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[retriever.Document, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for get_document

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_get_document_with_metadata`
        interceptor in new development instead of the `post_get_document` interceptor.
        When both interceptors are used, this `post_get_document_with_metadata` interceptor runs after the
        `post_get_document` interceptor. The (possibly modified) response returned by
        `post_get_document` will be passed to
        `post_get_document_with_metadata`.
        """
        return response, metadata

    def pre_list_chunks(
        self,
        request: retriever_service.ListChunksRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.ListChunksRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for list_chunks

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_list_chunks(
        self, response: retriever_service.ListChunksResponse
    ) -> retriever_service.ListChunksResponse:
        """Post-rpc interceptor for list_chunks

        DEPRECATED. Please use the `post_list_chunks_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_list_chunks` interceptor runs
        before the `post_list_chunks_with_metadata` interceptor.
        """
        return response

    def post_list_chunks_with_metadata(
        self,
        response: retriever_service.ListChunksResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.ListChunksResponse, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for list_chunks

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_list_chunks_with_metadata`
        interceptor in new development instead of the `post_list_chunks` interceptor.
        When both interceptors are used, this `post_list_chunks_with_metadata` interceptor runs after the
        `post_list_chunks` interceptor. The (possibly modified) response returned by
        `post_list_chunks` will be passed to
        `post_list_chunks_with_metadata`.
        """
        return response, metadata

    def pre_list_corpora(
        self,
        request: retriever_service.ListCorporaRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.ListCorporaRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for list_corpora

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_list_corpora(
        self, response: retriever_service.ListCorporaResponse
    ) -> retriever_service.ListCorporaResponse:
        """Post-rpc interceptor for list_corpora

        DEPRECATED. Please use the `post_list_corpora_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_list_corpora` interceptor runs
        before the `post_list_corpora_with_metadata` interceptor.
        """
        return response

    def post_list_corpora_with_metadata(
        self,
        response: retriever_service.ListCorporaResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.ListCorporaResponse, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for list_corpora

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_list_corpora_with_metadata`
        interceptor in new development instead of the `post_list_corpora` interceptor.
        When both interceptors are used, this `post_list_corpora_with_metadata` interceptor runs after the
        `post_list_corpora` interceptor. The (possibly modified) response returned by
        `post_list_corpora` will be passed to
        `post_list_corpora_with_metadata`.
        """
        return response, metadata

    def pre_list_documents(
        self,
        request: retriever_service.ListDocumentsRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.ListDocumentsRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for list_documents

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_list_documents(
        self, response: retriever_service.ListDocumentsResponse
    ) -> retriever_service.ListDocumentsResponse:
        """Post-rpc interceptor for list_documents

        DEPRECATED. Please use the `post_list_documents_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_list_documents` interceptor runs
        before the `post_list_documents_with_metadata` interceptor.
        """
        return response

    def post_list_documents_with_metadata(
        self,
        response: retriever_service.ListDocumentsResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.ListDocumentsResponse, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for list_documents

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_list_documents_with_metadata`
        interceptor in new development instead of the `post_list_documents` interceptor.
        When both interceptors are used, this `post_list_documents_with_metadata` interceptor runs after the
        `post_list_documents` interceptor. The (possibly modified) response returned by
        `post_list_documents` will be passed to
        `post_list_documents_with_metadata`.
        """
        return response, metadata

    def pre_query_corpus(
        self,
        request: retriever_service.QueryCorpusRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.QueryCorpusRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for query_corpus

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_query_corpus(
        self, response: retriever_service.QueryCorpusResponse
    ) -> retriever_service.QueryCorpusResponse:
        """Post-rpc interceptor for query_corpus

        DEPRECATED. Please use the `post_query_corpus_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_query_corpus` interceptor runs
        before the `post_query_corpus_with_metadata` interceptor.
        """
        return response

    def post_query_corpus_with_metadata(
        self,
        response: retriever_service.QueryCorpusResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.QueryCorpusResponse, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for query_corpus

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_query_corpus_with_metadata`
        interceptor in new development instead of the `post_query_corpus` interceptor.
        When both interceptors are used, this `post_query_corpus_with_metadata` interceptor runs after the
        `post_query_corpus` interceptor. The (possibly modified) response returned by
        `post_query_corpus` will be passed to
        `post_query_corpus_with_metadata`.
        """
        return response, metadata

    def pre_query_document(
        self,
        request: retriever_service.QueryDocumentRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.QueryDocumentRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for query_document

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_query_document(
        self, response: retriever_service.QueryDocumentResponse
    ) -> retriever_service.QueryDocumentResponse:
        """Post-rpc interceptor for query_document

        DEPRECATED. Please use the `post_query_document_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_query_document` interceptor runs
        before the `post_query_document_with_metadata` interceptor.
        """
        return response

    def post_query_document_with_metadata(
        self,
        response: retriever_service.QueryDocumentResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.QueryDocumentResponse, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for query_document

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_query_document_with_metadata`
        interceptor in new development instead of the `post_query_document` interceptor.
        When both interceptors are used, this `post_query_document_with_metadata` interceptor runs after the
        `post_query_document` interceptor. The (possibly modified) response returned by
        `post_query_document` will be passed to
        `post_query_document_with_metadata`.
        """
        return response, metadata

    def pre_update_chunk(
        self,
        request: retriever_service.UpdateChunkRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.UpdateChunkRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for update_chunk

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_update_chunk(self, response: retriever.Chunk) -> retriever.Chunk:
        """Post-rpc interceptor for update_chunk

        DEPRECATED. Please use the `post_update_chunk_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_update_chunk` interceptor runs
        before the `post_update_chunk_with_metadata` interceptor.
        """
        return response

    def post_update_chunk_with_metadata(
        self,
        response: retriever.Chunk,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[retriever.Chunk, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for update_chunk

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_update_chunk_with_metadata`
        interceptor in new development instead of the `post_update_chunk` interceptor.
        When both interceptors are used, this `post_update_chunk_with_metadata` interceptor runs after the
        `post_update_chunk` interceptor. The (possibly modified) response returned by
        `post_update_chunk` will be passed to
        `post_update_chunk_with_metadata`.
        """
        return response, metadata

    def pre_update_corpus(
        self,
        request: retriever_service.UpdateCorpusRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.UpdateCorpusRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for update_corpus

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_update_corpus(self, response: retriever.Corpus) -> retriever.Corpus:
        """Post-rpc interceptor for update_corpus

        DEPRECATED. Please use the `post_update_corpus_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_update_corpus` interceptor runs
        before the `post_update_corpus_with_metadata` interceptor.
        """
        return response

    def post_update_corpus_with_metadata(
        self,
        response: retriever.Corpus,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[retriever.Corpus, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for update_corpus

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_update_corpus_with_metadata`
        interceptor in new development instead of the `post_update_corpus` interceptor.
        When both interceptors are used, this `post_update_corpus_with_metadata` interceptor runs after the
        `post_update_corpus` interceptor. The (possibly modified) response returned by
        `post_update_corpus` will be passed to
        `post_update_corpus_with_metadata`.
        """
        return response, metadata

    def pre_update_document(
        self,
        request: retriever_service.UpdateDocumentRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        retriever_service.UpdateDocumentRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for update_document

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_update_document(self, response: retriever.Document) -> retriever.Document:
        """Post-rpc interceptor for update_document

        DEPRECATED. Please use the `post_update_document_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code. This `post_update_document` interceptor runs
        before the `post_update_document_with_metadata` interceptor.
        """
        return response

    def post_update_document_with_metadata(
        self,
        response: retriever.Document,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[retriever.Document, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for update_document

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the RetrieverService server but before it is returned to user code.

        We recommend only using this `post_update_document_with_metadata`
        interceptor in new development instead of the `post_update_document` interceptor.
        When both interceptors are used, this `post_update_document_with_metadata` interceptor runs after the
        `post_update_document` interceptor. The (possibly modified) response returned by
        `post_update_document` will be passed to
        `post_update_document_with_metadata`.
        """
        return response, metadata

    def pre_get_operation(
        self,
        request: operations_pb2.GetOperationRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        operations_pb2.GetOperationRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for get_operation

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_get_operation(
        self, response: operations_pb2.Operation
    ) -> operations_pb2.Operation:
        """Post-rpc interceptor for get_operation

        Override in a subclass to manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code.
        """
        return response

    def pre_list_operations(
        self,
        request: operations_pb2.ListOperationsRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        operations_pb2.ListOperationsRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for list_operations

        Override in a subclass to manipulate the request or metadata
        before they are sent to the RetrieverService server.
        """
        return request, metadata

    def post_list_operations(
        self, response: operations_pb2.ListOperationsResponse
    ) -> operations_pb2.ListOperationsResponse:
        """Post-rpc interceptor for list_operations

        Override in a subclass to manipulate the response
        after it is returned by the RetrieverService server but before
        it is returned to user code.
        """
        return response


@dataclasses.dataclass
class RetrieverServiceRestStub:
    _session: AuthorizedSession
    _host: str
    _interceptor: RetrieverServiceRestInterceptor


class RetrieverServiceRestTransport(_BaseRetrieverServiceRestTransport):
    """REST backend synchronous transport for RetrieverService.

    An API for semantic search over a corpus of user uploaded
    content.

    This class defines the same methods as the primary client, so the
    primary client can load the underlying transport implementation
    and call it.

    It sends JSON representations of protocol buffers over HTTP/1.1
    """

    def __init__(
        self,
        *,
        host: str = "generativelanguage.googleapis.com",
        credentials: Optional[ga_credentials.Credentials] = None,
        credentials_file: Optional[str] = None,
        scopes: Optional[Sequence[str]] = None,
        client_cert_source_for_mtls: Optional[Callable[[], Tuple[bytes, bytes]]] = None,
        quota_project_id: Optional[str] = None,
        client_info: gapic_v1.client_info.ClientInfo = DEFAULT_CLIENT_INFO,
        always_use_jwt_access: Optional[bool] = False,
        url_scheme: str = "https",
        interceptor: Optional[RetrieverServiceRestInterceptor] = None,
        api_audience: Optional[str] = None,
    ) -> None:
        """Instantiate the transport.

        Args:
            host (Optional[str]):
                 The hostname to connect to (default: 'generativelanguage.googleapis.com').
            credentials (Optional[google.auth.credentials.Credentials]): The
                authorization credentials to attach to requests. These
                credentials identify the application to the service; if none
                are specified, the client will attempt to ascertain the
                credentials from the environment.

            credentials_file (Optional[str]): A file with credentials that can
                be loaded with :func:`google.auth.load_credentials_from_file`.
                This argument is ignored if ``channel`` is provided.
            scopes (Optional(Sequence[str])): A list of scopes. This argument is
                ignored if ``channel`` is provided.
            client_cert_source_for_mtls (Callable[[], Tuple[bytes, bytes]]): Client
                certificate to configure mutual TLS HTTP channel. It is ignored
                if ``channel`` is provided.
            quota_project_id (Optional[str]): An optional project to use for billing
                and quota.
            client_info (google.api_core.gapic_v1.client_info.ClientInfo):
                The client info used to send a user-agent string along with
                API requests. If ``None``, then default info will be used.
                Generally, you only need to set this if you are developing
                your own client library.
            always_use_jwt_access (Optional[bool]): Whether self signed JWT should
                be used for service account credentials.
            url_scheme: the protocol scheme for the API endpoint.  Normally
                "https", but for testing or local servers,
                "http" can be specified.
        """
        # Run the base constructor
        # TODO(yon-mg): resolve other ctor params i.e. scopes, quota, etc.
        # TODO: When custom host (api_endpoint) is set, `scopes` must *also* be set on the
        # credentials object
        super().__init__(
            host=host,
            credentials=credentials,
            client_info=client_info,
            always_use_jwt_access=always_use_jwt_access,
            url_scheme=url_scheme,
            api_audience=api_audience,
        )
        self._session = AuthorizedSession(
            self._credentials, default_host=self.DEFAULT_HOST
        )
        if client_cert_source_for_mtls:
            self._session.configure_mtls_channel(client_cert_source_for_mtls)
        self._interceptor = interceptor or RetrieverServiceRestInterceptor()
        self._prep_wrapped_messages(client_info)

    class _BatchCreateChunks(
        _BaseRetrieverServiceRestTransport._BaseBatchCreateChunks,
        RetrieverServiceRestStub,
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.BatchCreateChunks")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
                data=body,
            )
            return response

        def __call__(
            self,
            request: retriever_service.BatchCreateChunksRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever_service.BatchCreateChunksResponse:
            r"""Call the batch create chunks method over HTTP.

            Args:
                request (~.retriever_service.BatchCreateChunksRequest):
                    The request object. Request to batch create ``Chunk``\ s.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever_service.BatchCreateChunksResponse:
                    Response from ``BatchCreateChunks`` containing a list of
                created ``Chunk``\ s.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseBatchCreateChunks._get_http_options()
            )

            request, metadata = self._interceptor.pre_batch_create_chunks(
                request, metadata
            )
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseBatchCreateChunks._get_transcoded_request(
                http_options, request
            )

            body = _BaseRetrieverServiceRestTransport._BaseBatchCreateChunks._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseBatchCreateChunks._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.BatchCreateChunks",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "BatchCreateChunks",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._BatchCreateChunks._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
                body,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever_service.BatchCreateChunksResponse()
            pb_resp = retriever_service.BatchCreateChunksResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_batch_create_chunks(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_batch_create_chunks_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = (
                        retriever_service.BatchCreateChunksResponse.to_json(response)
                    )
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.batch_create_chunks",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "BatchCreateChunks",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _BatchDeleteChunks(
        _BaseRetrieverServiceRestTransport._BaseBatchDeleteChunks,
        RetrieverServiceRestStub,
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.BatchDeleteChunks")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
                data=body,
            )
            return response

        def __call__(
            self,
            request: retriever_service.BatchDeleteChunksRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ):
            r"""Call the batch delete chunks method over HTTP.

            Args:
                request (~.retriever_service.BatchDeleteChunksRequest):
                    The request object. Request to batch delete ``Chunk``\ s.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.
            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseBatchDeleteChunks._get_http_options()
            )

            request, metadata = self._interceptor.pre_batch_delete_chunks(
                request, metadata
            )
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseBatchDeleteChunks._get_transcoded_request(
                http_options, request
            )

            body = _BaseRetrieverServiceRestTransport._BaseBatchDeleteChunks._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseBatchDeleteChunks._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = json_format.MessageToJson(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.BatchDeleteChunks",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "BatchDeleteChunks",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._BatchDeleteChunks._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
                body,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

    class _BatchUpdateChunks(
        _BaseRetrieverServiceRestTransport._BaseBatchUpdateChunks,
        RetrieverServiceRestStub,
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.BatchUpdateChunks")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
                data=body,
            )
            return response

        def __call__(
            self,
            request: retriever_service.BatchUpdateChunksRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever_service.BatchUpdateChunksResponse:
            r"""Call the batch update chunks method over HTTP.

            Args:
                request (~.retriever_service.BatchUpdateChunksRequest):
                    The request object. Request to batch update ``Chunk``\ s.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever_service.BatchUpdateChunksResponse:
                    Response from ``BatchUpdateChunks`` containing a list of
                updated ``Chunk``\ s.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseBatchUpdateChunks._get_http_options()
            )

            request, metadata = self._interceptor.pre_batch_update_chunks(
                request, metadata
            )
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseBatchUpdateChunks._get_transcoded_request(
                http_options, request
            )

            body = _BaseRetrieverServiceRestTransport._BaseBatchUpdateChunks._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseBatchUpdateChunks._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.BatchUpdateChunks",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "BatchUpdateChunks",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._BatchUpdateChunks._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
                body,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever_service.BatchUpdateChunksResponse()
            pb_resp = retriever_service.BatchUpdateChunksResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_batch_update_chunks(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_batch_update_chunks_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = (
                        retriever_service.BatchUpdateChunksResponse.to_json(response)
                    )
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.batch_update_chunks",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "BatchUpdateChunks",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _CreateChunk(
        _BaseRetrieverServiceRestTransport._BaseCreateChunk, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.CreateChunk")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
                data=body,
            )
            return response

        def __call__(
            self,
            request: retriever_service.CreateChunkRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever.Chunk:
            r"""Call the create chunk method over HTTP.

            Args:
                request (~.retriever_service.CreateChunkRequest):
                    The request object. Request to create a ``Chunk``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever.Chunk:
                    A ``Chunk`` is a subpart of a ``Document`` that is
                treated as an independent unit for the purposes of
                vector representation and storage. A ``Corpus`` can have
                a maximum of 1 million ``Chunk``\ s.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseCreateChunk._get_http_options()
            )

            request, metadata = self._interceptor.pre_create_chunk(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseCreateChunk._get_transcoded_request(
                http_options, request
            )

            body = _BaseRetrieverServiceRestTransport._BaseCreateChunk._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseCreateChunk._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.CreateChunk",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "CreateChunk",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._CreateChunk._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
                body,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever.Chunk()
            pb_resp = retriever.Chunk.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_create_chunk(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_create_chunk_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever.Chunk.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.create_chunk",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "CreateChunk",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _CreateCorpus(
        _BaseRetrieverServiceRestTransport._BaseCreateCorpus, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.CreateCorpus")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
                data=body,
            )
            return response

        def __call__(
            self,
            request: retriever_service.CreateCorpusRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever.Corpus:
            r"""Call the create corpus method over HTTP.

            Args:
                request (~.retriever_service.CreateCorpusRequest):
                    The request object. Request to create a ``Corpus``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever.Corpus:
                    A ``Corpus`` is a collection of ``Document``\ s. A
                project can create up to 5 corpora.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseCreateCorpus._get_http_options()
            )

            request, metadata = self._interceptor.pre_create_corpus(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseCreateCorpus._get_transcoded_request(
                http_options, request
            )

            body = _BaseRetrieverServiceRestTransport._BaseCreateCorpus._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseCreateCorpus._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.CreateCorpus",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "CreateCorpus",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._CreateCorpus._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
                body,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever.Corpus()
            pb_resp = retriever.Corpus.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_create_corpus(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_create_corpus_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever.Corpus.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.create_corpus",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "CreateCorpus",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _CreateDocument(
        _BaseRetrieverServiceRestTransport._BaseCreateDocument, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.CreateDocument")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
                data=body,
            )
            return response

        def __call__(
            self,
            request: retriever_service.CreateDocumentRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever.Document:
            r"""Call the create document method over HTTP.

            Args:
                request (~.retriever_service.CreateDocumentRequest):
                    The request object. Request to create a ``Document``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever.Document:
                    A ``Document`` is a collection of ``Chunk``\ s. A
                ``Corpus`` can have a maximum of 10,000 ``Document``\ s.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseCreateDocument._get_http_options()
            )

            request, metadata = self._interceptor.pre_create_document(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseCreateDocument._get_transcoded_request(
                http_options, request
            )

            body = _BaseRetrieverServiceRestTransport._BaseCreateDocument._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseCreateDocument._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.CreateDocument",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "CreateDocument",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._CreateDocument._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
                body,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever.Document()
            pb_resp = retriever.Document.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_create_document(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_create_document_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever.Document.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.create_document",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "CreateDocument",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _DeleteChunk(
        _BaseRetrieverServiceRestTransport._BaseDeleteChunk, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.DeleteChunk")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
            )
            return response

        def __call__(
            self,
            request: retriever_service.DeleteChunkRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ):
            r"""Call the delete chunk method over HTTP.

            Args:
                request (~.retriever_service.DeleteChunkRequest):
                    The request object. Request to delete a ``Chunk``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.
            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseDeleteChunk._get_http_options()
            )

            request, metadata = self._interceptor.pre_delete_chunk(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseDeleteChunk._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseDeleteChunk._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = json_format.MessageToJson(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.DeleteChunk",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "DeleteChunk",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._DeleteChunk._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

    class _DeleteCorpus(
        _BaseRetrieverServiceRestTransport._BaseDeleteCorpus, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.DeleteCorpus")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
            )
            return response

        def __call__(
            self,
            request: retriever_service.DeleteCorpusRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ):
            r"""Call the delete corpus method over HTTP.

            Args:
                request (~.retriever_service.DeleteCorpusRequest):
                    The request object. Request to delete a ``Corpus``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.
            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseDeleteCorpus._get_http_options()
            )

            request, metadata = self._interceptor.pre_delete_corpus(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseDeleteCorpus._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseDeleteCorpus._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = json_format.MessageToJson(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.DeleteCorpus",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "DeleteCorpus",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._DeleteCorpus._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

    class _DeleteDocument(
        _BaseRetrieverServiceRestTransport._BaseDeleteDocument, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.DeleteDocument")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
            )
            return response

        def __call__(
            self,
            request: retriever_service.DeleteDocumentRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ):
            r"""Call the delete document method over HTTP.

            Args:
                request (~.retriever_service.DeleteDocumentRequest):
                    The request object. Request to delete a ``Document``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.
            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseDeleteDocument._get_http_options()
            )

            request, metadata = self._interceptor.pre_delete_document(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseDeleteDocument._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseDeleteDocument._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = json_format.MessageToJson(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.DeleteDocument",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "DeleteDocument",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._DeleteDocument._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

    class _GetChunk(
        _BaseRetrieverServiceRestTransport._BaseGetChunk, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.GetChunk")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
            )
            return response

        def __call__(
            self,
            request: retriever_service.GetChunkRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever.Chunk:
            r"""Call the get chunk method over HTTP.

            Args:
                request (~.retriever_service.GetChunkRequest):
                    The request object. Request for getting information about a specific
                ``Chunk``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever.Chunk:
                    A ``Chunk`` is a subpart of a ``Document`` that is
                treated as an independent unit for the purposes of
                vector representation and storage. A ``Corpus`` can have
                a maximum of 1 million ``Chunk``\ s.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseGetChunk._get_http_options()
            )

            request, metadata = self._interceptor.pre_get_chunk(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseGetChunk._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = (
                _BaseRetrieverServiceRestTransport._BaseGetChunk._get_query_params_json(
                    transcoded_request
                )
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.GetChunk",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "GetChunk",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._GetChunk._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever.Chunk()
            pb_resp = retriever.Chunk.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_get_chunk(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_get_chunk_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever.Chunk.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.get_chunk",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "GetChunk",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _GetCorpus(
        _BaseRetrieverServiceRestTransport._BaseGetCorpus, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.GetCorpus")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
            )
            return response

        def __call__(
            self,
            request: retriever_service.GetCorpusRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever.Corpus:
            r"""Call the get corpus method over HTTP.

            Args:
                request (~.retriever_service.GetCorpusRequest):
                    The request object. Request for getting information about a specific
                ``Corpus``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever.Corpus:
                    A ``Corpus`` is a collection of ``Document``\ s. A
                project can create up to 5 corpora.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseGetCorpus._get_http_options()
            )

            request, metadata = self._interceptor.pre_get_corpus(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseGetCorpus._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseGetCorpus._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.GetCorpus",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "GetCorpus",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._GetCorpus._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever.Corpus()
            pb_resp = retriever.Corpus.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_get_corpus(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_get_corpus_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever.Corpus.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.get_corpus",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "GetCorpus",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _GetDocument(
        _BaseRetrieverServiceRestTransport._BaseGetDocument, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.GetDocument")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
            )
            return response

        def __call__(
            self,
            request: retriever_service.GetDocumentRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever.Document:
            r"""Call the get document method over HTTP.

            Args:
                request (~.retriever_service.GetDocumentRequest):
                    The request object. Request for getting information about a specific
                ``Document``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever.Document:
                    A ``Document`` is a collection of ``Chunk``\ s. A
                ``Corpus`` can have a maximum of 10,000 ``Document``\ s.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseGetDocument._get_http_options()
            )

            request, metadata = self._interceptor.pre_get_document(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseGetDocument._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseGetDocument._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.GetDocument",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "GetDocument",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._GetDocument._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever.Document()
            pb_resp = retriever.Document.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_get_document(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_get_document_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever.Document.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.get_document",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "GetDocument",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _ListChunks(
        _BaseRetrieverServiceRestTransport._BaseListChunks, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.ListChunks")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
            )
            return response

        def __call__(
            self,
            request: retriever_service.ListChunksRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever_service.ListChunksResponse:
            r"""Call the list chunks method over HTTP.

            Args:
                request (~.retriever_service.ListChunksRequest):
                    The request object. Request for listing ``Chunk``\ s.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever_service.ListChunksResponse:
                    Response from ``ListChunks`` containing a paginated list
                of ``Chunk``\ s. The ``Chunk``\ s are sorted by
                ascending ``chunk.create_time``.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseListChunks._get_http_options()
            )

            request, metadata = self._interceptor.pre_list_chunks(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseListChunks._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseListChunks._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.ListChunks",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "ListChunks",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._ListChunks._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever_service.ListChunksResponse()
            pb_resp = retriever_service.ListChunksResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_list_chunks(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_list_chunks_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever_service.ListChunksResponse.to_json(
                        response
                    )
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.list_chunks",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "ListChunks",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _ListCorpora(
        _BaseRetrieverServiceRestTransport._BaseListCorpora, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.ListCorpora")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
            )
            return response

        def __call__(
            self,
            request: retriever_service.ListCorporaRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever_service.ListCorporaResponse:
            r"""Call the list corpora method over HTTP.

            Args:
                request (~.retriever_service.ListCorporaRequest):
                    The request object. Request for listing ``Corpora``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever_service.ListCorporaResponse:
                    Response from ``ListCorpora`` containing a paginated
                list of ``Corpora``. The results are sorted by ascending
                ``corpus.create_time``.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseListCorpora._get_http_options()
            )

            request, metadata = self._interceptor.pre_list_corpora(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseListCorpora._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseListCorpora._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.ListCorpora",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "ListCorpora",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._ListCorpora._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever_service.ListCorporaResponse()
            pb_resp = retriever_service.ListCorporaResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_list_corpora(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_list_corpora_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever_service.ListCorporaResponse.to_json(
                        response
                    )
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.list_corpora",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "ListCorpora",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _ListDocuments(
        _BaseRetrieverServiceRestTransport._BaseListDocuments, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.ListDocuments")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
            )
            return response

        def __call__(
            self,
            request: retriever_service.ListDocumentsRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever_service.ListDocumentsResponse:
            r"""Call the list documents method over HTTP.

            Args:
                request (~.retriever_service.ListDocumentsRequest):
                    The request object. Request for listing ``Document``\ s.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever_service.ListDocumentsResponse:
                    Response from ``ListDocuments`` containing a paginated
                list of ``Document``\ s. The ``Document``\ s are sorted
                by ascending ``document.create_time``.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseListDocuments._get_http_options()
            )

            request, metadata = self._interceptor.pre_list_documents(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseListDocuments._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseListDocuments._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.ListDocuments",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "ListDocuments",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._ListDocuments._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever_service.ListDocumentsResponse()
            pb_resp = retriever_service.ListDocumentsResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_list_documents(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_list_documents_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever_service.ListDocumentsResponse.to_json(
                        response
                    )
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.list_documents",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "ListDocuments",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _QueryCorpus(
        _BaseRetrieverServiceRestTransport._BaseQueryCorpus, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.QueryCorpus")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
                data=body,
            )
            return response

        def __call__(
            self,
            request: retriever_service.QueryCorpusRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever_service.QueryCorpusResponse:
            r"""Call the query corpus method over HTTP.

            Args:
                request (~.retriever_service.QueryCorpusRequest):
                    The request object. Request for querying a ``Corpus``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever_service.QueryCorpusResponse:
                    Response from ``QueryCorpus`` containing a list of
                relevant chunks.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseQueryCorpus._get_http_options()
            )

            request, metadata = self._interceptor.pre_query_corpus(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseQueryCorpus._get_transcoded_request(
                http_options, request
            )

            body = _BaseRetrieverServiceRestTransport._BaseQueryCorpus._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseQueryCorpus._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.QueryCorpus",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "QueryCorpus",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._QueryCorpus._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
                body,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever_service.QueryCorpusResponse()
            pb_resp = retriever_service.QueryCorpusResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_query_corpus(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_query_corpus_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever_service.QueryCorpusResponse.to_json(
                        response
                    )
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.query_corpus",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "QueryCorpus",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _QueryDocument(
        _BaseRetrieverServiceRestTransport._BaseQueryDocument, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.QueryDocument")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
                data=body,
            )
            return response

        def __call__(
            self,
            request: retriever_service.QueryDocumentRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever_service.QueryDocumentResponse:
            r"""Call the query document method over HTTP.

            Args:
                request (~.retriever_service.QueryDocumentRequest):
                    The request object. Request for querying a ``Document``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever_service.QueryDocumentResponse:
                    Response from ``QueryDocument`` containing a list of
                relevant chunks.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseQueryDocument._get_http_options()
            )

            request, metadata = self._interceptor.pre_query_document(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseQueryDocument._get_transcoded_request(
                http_options, request
            )

            body = _BaseRetrieverServiceRestTransport._BaseQueryDocument._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseQueryDocument._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.QueryDocument",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "QueryDocument",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._QueryDocument._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
                body,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever_service.QueryDocumentResponse()
            pb_resp = retriever_service.QueryDocumentResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_query_document(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_query_document_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever_service.QueryDocumentResponse.to_json(
                        response
                    )
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.query_document",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "QueryDocument",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _UpdateChunk(
        _BaseRetrieverServiceRestTransport._BaseUpdateChunk, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.UpdateChunk")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
                data=body,
            )
            return response

        def __call__(
            self,
            request: retriever_service.UpdateChunkRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever.Chunk:
            r"""Call the update chunk method over HTTP.

            Args:
                request (~.retriever_service.UpdateChunkRequest):
                    The request object. Request to update a ``Chunk``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever.Chunk:
                    A ``Chunk`` is a subpart of a ``Document`` that is
                treated as an independent unit for the purposes of
                vector representation and storage. A ``Corpus`` can have
                a maximum of 1 million ``Chunk``\ s.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseUpdateChunk._get_http_options()
            )

            request, metadata = self._interceptor.pre_update_chunk(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseUpdateChunk._get_transcoded_request(
                http_options, request
            )

            body = _BaseRetrieverServiceRestTransport._BaseUpdateChunk._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseUpdateChunk._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.UpdateChunk",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "UpdateChunk",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._UpdateChunk._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
                body,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever.Chunk()
            pb_resp = retriever.Chunk.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_update_chunk(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_update_chunk_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever.Chunk.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.update_chunk",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "UpdateChunk",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _UpdateCorpus(
        _BaseRetrieverServiceRestTransport._BaseUpdateCorpus, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.UpdateCorpus")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
                data=body,
            )
            return response

        def __call__(
            self,
            request: retriever_service.UpdateCorpusRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever.Corpus:
            r"""Call the update corpus method over HTTP.

            Args:
                request (~.retriever_service.UpdateCorpusRequest):
                    The request object. Request to update a ``Corpus``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever.Corpus:
                    A ``Corpus`` is a collection of ``Document``\ s. A
                project can create up to 5 corpora.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseUpdateCorpus._get_http_options()
            )

            request, metadata = self._interceptor.pre_update_corpus(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseUpdateCorpus._get_transcoded_request(
                http_options, request
            )

            body = _BaseRetrieverServiceRestTransport._BaseUpdateCorpus._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseUpdateCorpus._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.UpdateCorpus",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "UpdateCorpus",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._UpdateCorpus._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
                body,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever.Corpus()
            pb_resp = retriever.Corpus.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_update_corpus(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_update_corpus_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever.Corpus.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.update_corpus",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "UpdateCorpus",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _UpdateDocument(
        _BaseRetrieverServiceRestTransport._BaseUpdateDocument, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.UpdateDocument")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
                data=body,
            )
            return response

        def __call__(
            self,
            request: retriever_service.UpdateDocumentRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> retriever.Document:
            r"""Call the update document method over HTTP.

            Args:
                request (~.retriever_service.UpdateDocumentRequest):
                    The request object. Request to update a ``Document``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.retriever.Document:
                    A ``Document`` is a collection of ``Chunk``\ s. A
                ``Corpus`` can have a maximum of 10,000 ``Document``\ s.

            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseUpdateDocument._get_http_options()
            )

            request, metadata = self._interceptor.pre_update_document(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseUpdateDocument._get_transcoded_request(
                http_options, request
            )

            body = _BaseRetrieverServiceRestTransport._BaseUpdateDocument._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseUpdateDocument._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = type(request).to_json(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.UpdateDocument",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "UpdateDocument",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._UpdateDocument._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
                body,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = retriever.Document()
            pb_resp = retriever.Document.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_update_document(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_update_document_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = retriever.Document.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceClient.update_document",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "UpdateDocument",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    @property
    def batch_create_chunks(
        self,
    ) -> Callable[
        [retriever_service.BatchCreateChunksRequest],
        retriever_service.BatchCreateChunksResponse,
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._BatchCreateChunks(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def batch_delete_chunks(
        self,
    ) -> Callable[[retriever_service.BatchDeleteChunksRequest], empty_pb2.Empty]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._BatchDeleteChunks(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def batch_update_chunks(
        self,
    ) -> Callable[
        [retriever_service.BatchUpdateChunksRequest],
        retriever_service.BatchUpdateChunksResponse,
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._BatchUpdateChunks(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def create_chunk(
        self,
    ) -> Callable[[retriever_service.CreateChunkRequest], retriever.Chunk]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._CreateChunk(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def create_corpus(
        self,
    ) -> Callable[[retriever_service.CreateCorpusRequest], retriever.Corpus]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._CreateCorpus(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def create_document(
        self,
    ) -> Callable[[retriever_service.CreateDocumentRequest], retriever.Document]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._CreateDocument(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def delete_chunk(
        self,
    ) -> Callable[[retriever_service.DeleteChunkRequest], empty_pb2.Empty]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._DeleteChunk(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def delete_corpus(
        self,
    ) -> Callable[[retriever_service.DeleteCorpusRequest], empty_pb2.Empty]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._DeleteCorpus(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def delete_document(
        self,
    ) -> Callable[[retriever_service.DeleteDocumentRequest], empty_pb2.Empty]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._DeleteDocument(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def get_chunk(
        self,
    ) -> Callable[[retriever_service.GetChunkRequest], retriever.Chunk]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._GetChunk(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def get_corpus(
        self,
    ) -> Callable[[retriever_service.GetCorpusRequest], retriever.Corpus]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._GetCorpus(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def get_document(
        self,
    ) -> Callable[[retriever_service.GetDocumentRequest], retriever.Document]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._GetDocument(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def list_chunks(
        self,
    ) -> Callable[
        [retriever_service.ListChunksRequest], retriever_service.ListChunksResponse
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._ListChunks(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def list_corpora(
        self,
    ) -> Callable[
        [retriever_service.ListCorporaRequest], retriever_service.ListCorporaResponse
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._ListCorpora(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def list_documents(
        self,
    ) -> Callable[
        [retriever_service.ListDocumentsRequest],
        retriever_service.ListDocumentsResponse,
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._ListDocuments(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def query_corpus(
        self,
    ) -> Callable[
        [retriever_service.QueryCorpusRequest], retriever_service.QueryCorpusResponse
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._QueryCorpus(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def query_document(
        self,
    ) -> Callable[
        [retriever_service.QueryDocumentRequest],
        retriever_service.QueryDocumentResponse,
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._QueryDocument(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def update_chunk(
        self,
    ) -> Callable[[retriever_service.UpdateChunkRequest], retriever.Chunk]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._UpdateChunk(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def update_corpus(
        self,
    ) -> Callable[[retriever_service.UpdateCorpusRequest], retriever.Corpus]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._UpdateCorpus(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def update_document(
        self,
    ) -> Callable[[retriever_service.UpdateDocumentRequest], retriever.Document]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._UpdateDocument(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def get_operation(self):
        return self._GetOperation(self._session, self._host, self._interceptor)  # type: ignore

    class _GetOperation(
        _BaseRetrieverServiceRestTransport._BaseGetOperation, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.GetOperation")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
            )
            return response

        def __call__(
            self,
            request: operations_pb2.GetOperationRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> operations_pb2.Operation:
            r"""Call the get operation method over HTTP.

            Args:
                request (operations_pb2.GetOperationRequest):
                    The request object for GetOperation method.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                operations_pb2.Operation: Response from GetOperation method.
            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseGetOperation._get_http_options()
            )

            request, metadata = self._interceptor.pre_get_operation(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseGetOperation._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseGetOperation._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = json_format.MessageToJson(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.GetOperation",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "GetOperation",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._GetOperation._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            content = response.content.decode("utf-8")
            resp = operations_pb2.Operation()
            resp = json_format.Parse(content, resp)
            resp = self._interceptor.post_get_operation(resp)
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = json_format.MessageToJson(resp)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceAsyncClient.GetOperation",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "GetOperation",
                        "httpResponse": http_response,
                        "metadata": http_response["headers"],
                    },
                )
            return resp

    @property
    def list_operations(self):
        return self._ListOperations(self._session, self._host, self._interceptor)  # type: ignore

    class _ListOperations(
        _BaseRetrieverServiceRestTransport._BaseListOperations, RetrieverServiceRestStub
    ):
        def __hash__(self):
            return hash("RetrieverServiceRestTransport.ListOperations")

        @staticmethod
        def _get_response(
            host,
            metadata,
            query_params,
            session,
            timeout,
            transcoded_request,
            body=None,
        ):
            uri = transcoded_request["uri"]
            method = transcoded_request["method"]
            headers = dict(metadata)
            headers["Content-Type"] = "application/json"
            response = getattr(session, method)(
                "{host}{uri}".format(host=host, uri=uri),
                timeout=timeout,
                headers=headers,
                params=rest_helpers.flatten_query_params(query_params, strict=True),
            )
            return response

        def __call__(
            self,
            request: operations_pb2.ListOperationsRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> operations_pb2.ListOperationsResponse:
            r"""Call the list operations method over HTTP.

            Args:
                request (operations_pb2.ListOperationsRequest):
                    The request object for ListOperations method.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                operations_pb2.ListOperationsResponse: Response from ListOperations method.
            """

            http_options = (
                _BaseRetrieverServiceRestTransport._BaseListOperations._get_http_options()
            )

            request, metadata = self._interceptor.pre_list_operations(request, metadata)
            transcoded_request = _BaseRetrieverServiceRestTransport._BaseListOperations._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseRetrieverServiceRestTransport._BaseListOperations._get_query_params_json(
                transcoded_request
            )

            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                request_url = "{host}{uri}".format(
                    host=self._host, uri=transcoded_request["uri"]
                )
                method = transcoded_request["method"]
                try:
                    request_payload = json_format.MessageToJson(request)
                except:
                    request_payload = None
                http_request = {
                    "payload": request_payload,
                    "requestMethod": method,
                    "requestUrl": request_url,
                    "headers": dict(metadata),
                }
                _LOGGER.debug(
                    f"Sending request for google.ai.generativelanguage_v1beta.RetrieverServiceClient.ListOperations",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "ListOperations",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = RetrieverServiceRestTransport._ListOperations._get_response(
                self._host,
                metadata,
                query_params,
                self._session,
                timeout,
                transcoded_request,
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            content = response.content.decode("utf-8")
            resp = operations_pb2.ListOperationsResponse()
            resp = json_format.Parse(content, resp)
            resp = self._interceptor.post_list_operations(resp)
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = json_format.MessageToJson(resp)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta.RetrieverServiceAsyncClient.ListOperations",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta.RetrieverService",
                        "rpcName": "ListOperations",
                        "httpResponse": http_response,
                        "metadata": http_response["headers"],
                    },
                )
            return resp

    @property
    def kind(self) -> str:
        return "rest"

    def close(self):
        self._session.close()


__all__ = ("RetrieverServiceRestTransport",)
