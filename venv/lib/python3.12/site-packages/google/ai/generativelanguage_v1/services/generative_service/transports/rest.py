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
from google.protobuf import json_format
from requests import __version__ as requests_version

from google.ai.generativelanguage_v1.types import generative_service

from .base import DEFAULT_CLIENT_INFO as BASE_DEFAULT_CLIENT_INFO
from .rest_base import _BaseGenerativeServiceRestTransport

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


class GenerativeServiceRestInterceptor:
    """Interceptor for GenerativeService.

    Interceptors are used to manipulate requests, request metadata, and responses
    in arbitrary ways.
    Example use cases include:
    * Logging
    * Verifying requests according to service or custom semantics
    * Stripping extraneous information from responses

    These use cases and more can be enabled by injecting an
    instance of a custom subclass when constructing the GenerativeServiceRestTransport.

    .. code-block:: python
        class MyCustomGenerativeServiceInterceptor(GenerativeServiceRestInterceptor):
            def pre_batch_embed_contents(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_batch_embed_contents(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_count_tokens(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_count_tokens(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_embed_content(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_embed_content(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_generate_content(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_generate_content(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_stream_generate_content(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_stream_generate_content(self, response):
                logging.log(f"Received response: {response}")
                return response

        transport = GenerativeServiceRestTransport(interceptor=MyCustomGenerativeServiceInterceptor())
        client = GenerativeServiceClient(transport=transport)


    """

    def pre_batch_embed_contents(
        self,
        request: generative_service.BatchEmbedContentsRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        generative_service.BatchEmbedContentsRequest,
        Sequence[Tuple[str, Union[str, bytes]]],
    ]:
        """Pre-rpc interceptor for batch_embed_contents

        Override in a subclass to manipulate the request or metadata
        before they are sent to the GenerativeService server.
        """
        return request, metadata

    def post_batch_embed_contents(
        self, response: generative_service.BatchEmbedContentsResponse
    ) -> generative_service.BatchEmbedContentsResponse:
        """Post-rpc interceptor for batch_embed_contents

        DEPRECATED. Please use the `post_batch_embed_contents_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the GenerativeService server but before
        it is returned to user code. This `post_batch_embed_contents` interceptor runs
        before the `post_batch_embed_contents_with_metadata` interceptor.
        """
        return response

    def post_batch_embed_contents_with_metadata(
        self,
        response: generative_service.BatchEmbedContentsResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        generative_service.BatchEmbedContentsResponse,
        Sequence[Tuple[str, Union[str, bytes]]],
    ]:
        """Post-rpc interceptor for batch_embed_contents

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the GenerativeService server but before it is returned to user code.

        We recommend only using this `post_batch_embed_contents_with_metadata`
        interceptor in new development instead of the `post_batch_embed_contents` interceptor.
        When both interceptors are used, this `post_batch_embed_contents_with_metadata` interceptor runs after the
        `post_batch_embed_contents` interceptor. The (possibly modified) response returned by
        `post_batch_embed_contents` will be passed to
        `post_batch_embed_contents_with_metadata`.
        """
        return response, metadata

    def pre_count_tokens(
        self,
        request: generative_service.CountTokensRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        generative_service.CountTokensRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for count_tokens

        Override in a subclass to manipulate the request or metadata
        before they are sent to the GenerativeService server.
        """
        return request, metadata

    def post_count_tokens(
        self, response: generative_service.CountTokensResponse
    ) -> generative_service.CountTokensResponse:
        """Post-rpc interceptor for count_tokens

        DEPRECATED. Please use the `post_count_tokens_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the GenerativeService server but before
        it is returned to user code. This `post_count_tokens` interceptor runs
        before the `post_count_tokens_with_metadata` interceptor.
        """
        return response

    def post_count_tokens_with_metadata(
        self,
        response: generative_service.CountTokensResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        generative_service.CountTokensResponse, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for count_tokens

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the GenerativeService server but before it is returned to user code.

        We recommend only using this `post_count_tokens_with_metadata`
        interceptor in new development instead of the `post_count_tokens` interceptor.
        When both interceptors are used, this `post_count_tokens_with_metadata` interceptor runs after the
        `post_count_tokens` interceptor. The (possibly modified) response returned by
        `post_count_tokens` will be passed to
        `post_count_tokens_with_metadata`.
        """
        return response, metadata

    def pre_embed_content(
        self,
        request: generative_service.EmbedContentRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        generative_service.EmbedContentRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for embed_content

        Override in a subclass to manipulate the request or metadata
        before they are sent to the GenerativeService server.
        """
        return request, metadata

    def post_embed_content(
        self, response: generative_service.EmbedContentResponse
    ) -> generative_service.EmbedContentResponse:
        """Post-rpc interceptor for embed_content

        DEPRECATED. Please use the `post_embed_content_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the GenerativeService server but before
        it is returned to user code. This `post_embed_content` interceptor runs
        before the `post_embed_content_with_metadata` interceptor.
        """
        return response

    def post_embed_content_with_metadata(
        self,
        response: generative_service.EmbedContentResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        generative_service.EmbedContentResponse, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for embed_content

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the GenerativeService server but before it is returned to user code.

        We recommend only using this `post_embed_content_with_metadata`
        interceptor in new development instead of the `post_embed_content` interceptor.
        When both interceptors are used, this `post_embed_content_with_metadata` interceptor runs after the
        `post_embed_content` interceptor. The (possibly modified) response returned by
        `post_embed_content` will be passed to
        `post_embed_content_with_metadata`.
        """
        return response, metadata

    def pre_generate_content(
        self,
        request: generative_service.GenerateContentRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        generative_service.GenerateContentRequest,
        Sequence[Tuple[str, Union[str, bytes]]],
    ]:
        """Pre-rpc interceptor for generate_content

        Override in a subclass to manipulate the request or metadata
        before they are sent to the GenerativeService server.
        """
        return request, metadata

    def post_generate_content(
        self, response: generative_service.GenerateContentResponse
    ) -> generative_service.GenerateContentResponse:
        """Post-rpc interceptor for generate_content

        DEPRECATED. Please use the `post_generate_content_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the GenerativeService server but before
        it is returned to user code. This `post_generate_content` interceptor runs
        before the `post_generate_content_with_metadata` interceptor.
        """
        return response

    def post_generate_content_with_metadata(
        self,
        response: generative_service.GenerateContentResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        generative_service.GenerateContentResponse,
        Sequence[Tuple[str, Union[str, bytes]]],
    ]:
        """Post-rpc interceptor for generate_content

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the GenerativeService server but before it is returned to user code.

        We recommend only using this `post_generate_content_with_metadata`
        interceptor in new development instead of the `post_generate_content` interceptor.
        When both interceptors are used, this `post_generate_content_with_metadata` interceptor runs after the
        `post_generate_content` interceptor. The (possibly modified) response returned by
        `post_generate_content` will be passed to
        `post_generate_content_with_metadata`.
        """
        return response, metadata

    def pre_stream_generate_content(
        self,
        request: generative_service.GenerateContentRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        generative_service.GenerateContentRequest,
        Sequence[Tuple[str, Union[str, bytes]]],
    ]:
        """Pre-rpc interceptor for stream_generate_content

        Override in a subclass to manipulate the request or metadata
        before they are sent to the GenerativeService server.
        """
        return request, metadata

    def post_stream_generate_content(
        self, response: rest_streaming.ResponseIterator
    ) -> rest_streaming.ResponseIterator:
        """Post-rpc interceptor for stream_generate_content

        DEPRECATED. Please use the `post_stream_generate_content_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the GenerativeService server but before
        it is returned to user code. This `post_stream_generate_content` interceptor runs
        before the `post_stream_generate_content_with_metadata` interceptor.
        """
        return response

    def post_stream_generate_content_with_metadata(
        self,
        response: rest_streaming.ResponseIterator,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        rest_streaming.ResponseIterator, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for stream_generate_content

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the GenerativeService server but before it is returned to user code.

        We recommend only using this `post_stream_generate_content_with_metadata`
        interceptor in new development instead of the `post_stream_generate_content` interceptor.
        When both interceptors are used, this `post_stream_generate_content_with_metadata` interceptor runs after the
        `post_stream_generate_content` interceptor. The (possibly modified) response returned by
        `post_stream_generate_content` will be passed to
        `post_stream_generate_content_with_metadata`.
        """
        return response, metadata

    def pre_cancel_operation(
        self,
        request: operations_pb2.CancelOperationRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        operations_pb2.CancelOperationRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for cancel_operation

        Override in a subclass to manipulate the request or metadata
        before they are sent to the GenerativeService server.
        """
        return request, metadata

    def post_cancel_operation(self, response: None) -> None:
        """Post-rpc interceptor for cancel_operation

        Override in a subclass to manipulate the response
        after it is returned by the GenerativeService server but before
        it is returned to user code.
        """
        return response

    def pre_get_operation(
        self,
        request: operations_pb2.GetOperationRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        operations_pb2.GetOperationRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for get_operation

        Override in a subclass to manipulate the request or metadata
        before they are sent to the GenerativeService server.
        """
        return request, metadata

    def post_get_operation(
        self, response: operations_pb2.Operation
    ) -> operations_pb2.Operation:
        """Post-rpc interceptor for get_operation

        Override in a subclass to manipulate the response
        after it is returned by the GenerativeService server but before
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
        before they are sent to the GenerativeService server.
        """
        return request, metadata

    def post_list_operations(
        self, response: operations_pb2.ListOperationsResponse
    ) -> operations_pb2.ListOperationsResponse:
        """Post-rpc interceptor for list_operations

        Override in a subclass to manipulate the response
        after it is returned by the GenerativeService server but before
        it is returned to user code.
        """
        return response


@dataclasses.dataclass
class GenerativeServiceRestStub:
    _session: AuthorizedSession
    _host: str
    _interceptor: GenerativeServiceRestInterceptor


class GenerativeServiceRestTransport(_BaseGenerativeServiceRestTransport):
    """REST backend synchronous transport for GenerativeService.

    API for using Large Models that generate multimodal content
    and have additional capabilities beyond text generation.

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
        interceptor: Optional[GenerativeServiceRestInterceptor] = None,
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
        self._interceptor = interceptor or GenerativeServiceRestInterceptor()
        self._prep_wrapped_messages(client_info)

    class _BatchEmbedContents(
        _BaseGenerativeServiceRestTransport._BaseBatchEmbedContents,
        GenerativeServiceRestStub,
    ):
        def __hash__(self):
            return hash("GenerativeServiceRestTransport.BatchEmbedContents")

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
            request: generative_service.BatchEmbedContentsRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> generative_service.BatchEmbedContentsResponse:
            r"""Call the batch embed contents method over HTTP.

            Args:
                request (~.generative_service.BatchEmbedContentsRequest):
                    The request object. Batch request to get embeddings from
                the model for a list of prompts.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.generative_service.BatchEmbedContentsResponse:
                    The response to a ``BatchEmbedContentsRequest``.
            """

            http_options = (
                _BaseGenerativeServiceRestTransport._BaseBatchEmbedContents._get_http_options()
            )

            request, metadata = self._interceptor.pre_batch_embed_contents(
                request, metadata
            )
            transcoded_request = _BaseGenerativeServiceRestTransport._BaseBatchEmbedContents._get_transcoded_request(
                http_options, request
            )

            body = _BaseGenerativeServiceRestTransport._BaseBatchEmbedContents._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseGenerativeServiceRestTransport._BaseBatchEmbedContents._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1.GenerativeServiceClient.BatchEmbedContents",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
                        "rpcName": "BatchEmbedContents",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = GenerativeServiceRestTransport._BatchEmbedContents._get_response(
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
            resp = generative_service.BatchEmbedContentsResponse()
            pb_resp = generative_service.BatchEmbedContentsResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_batch_embed_contents(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_batch_embed_contents_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = (
                        generative_service.BatchEmbedContentsResponse.to_json(response)
                    )
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1.GenerativeServiceClient.batch_embed_contents",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
                        "rpcName": "BatchEmbedContents",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _CountTokens(
        _BaseGenerativeServiceRestTransport._BaseCountTokens, GenerativeServiceRestStub
    ):
        def __hash__(self):
            return hash("GenerativeServiceRestTransport.CountTokens")

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
            request: generative_service.CountTokensRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> generative_service.CountTokensResponse:
            r"""Call the count tokens method over HTTP.

            Args:
                request (~.generative_service.CountTokensRequest):
                    The request object. Counts the number of tokens in the ``prompt`` sent to a
                model.

                Models may tokenize text differently, so each model may
                return a different ``token_count``.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.generative_service.CountTokensResponse:
                    A response from ``CountTokens``.

                It returns the model's ``token_count`` for the
                ``prompt``.

            """

            http_options = (
                _BaseGenerativeServiceRestTransport._BaseCountTokens._get_http_options()
            )

            request, metadata = self._interceptor.pre_count_tokens(request, metadata)
            transcoded_request = _BaseGenerativeServiceRestTransport._BaseCountTokens._get_transcoded_request(
                http_options, request
            )

            body = _BaseGenerativeServiceRestTransport._BaseCountTokens._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseGenerativeServiceRestTransport._BaseCountTokens._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1.GenerativeServiceClient.CountTokens",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
                        "rpcName": "CountTokens",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = GenerativeServiceRestTransport._CountTokens._get_response(
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
            resp = generative_service.CountTokensResponse()
            pb_resp = generative_service.CountTokensResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_count_tokens(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_count_tokens_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = generative_service.CountTokensResponse.to_json(
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
                    "Received response for google.ai.generativelanguage_v1.GenerativeServiceClient.count_tokens",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
                        "rpcName": "CountTokens",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _EmbedContent(
        _BaseGenerativeServiceRestTransport._BaseEmbedContent, GenerativeServiceRestStub
    ):
        def __hash__(self):
            return hash("GenerativeServiceRestTransport.EmbedContent")

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
            request: generative_service.EmbedContentRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> generative_service.EmbedContentResponse:
            r"""Call the embed content method over HTTP.

            Args:
                request (~.generative_service.EmbedContentRequest):
                    The request object. Request containing the ``Content`` for the model to
                embed.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.generative_service.EmbedContentResponse:
                    The response to an ``EmbedContentRequest``.
            """

            http_options = (
                _BaseGenerativeServiceRestTransport._BaseEmbedContent._get_http_options()
            )

            request, metadata = self._interceptor.pre_embed_content(request, metadata)
            transcoded_request = _BaseGenerativeServiceRestTransport._BaseEmbedContent._get_transcoded_request(
                http_options, request
            )

            body = _BaseGenerativeServiceRestTransport._BaseEmbedContent._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseGenerativeServiceRestTransport._BaseEmbedContent._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1.GenerativeServiceClient.EmbedContent",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
                        "rpcName": "EmbedContent",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = GenerativeServiceRestTransport._EmbedContent._get_response(
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
            resp = generative_service.EmbedContentResponse()
            pb_resp = generative_service.EmbedContentResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_embed_content(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_embed_content_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = generative_service.EmbedContentResponse.to_json(
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
                    "Received response for google.ai.generativelanguage_v1.GenerativeServiceClient.embed_content",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
                        "rpcName": "EmbedContent",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _GenerateContent(
        _BaseGenerativeServiceRestTransport._BaseGenerateContent,
        GenerativeServiceRestStub,
    ):
        def __hash__(self):
            return hash("GenerativeServiceRestTransport.GenerateContent")

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
            request: generative_service.GenerateContentRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> generative_service.GenerateContentResponse:
            r"""Call the generate content method over HTTP.

            Args:
                request (~.generative_service.GenerateContentRequest):
                    The request object. Request to generate a completion from
                the model.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.generative_service.GenerateContentResponse:
                    Response from the model supporting multiple candidate
                responses.

                Safety ratings and content filtering are reported for
                both prompt in
                ``GenerateContentResponse.prompt_feedback`` and for each
                candidate in ``finish_reason`` and in
                ``safety_ratings``. The API:

                -  Returns either all requested candidates or none of
                   them
                -  Returns no candidates at all only if there was
                   something wrong with the prompt (check
                   ``prompt_feedback``)
                -  Reports feedback on each candidate in
                   ``finish_reason`` and ``safety_ratings``.

            """

            http_options = (
                _BaseGenerativeServiceRestTransport._BaseGenerateContent._get_http_options()
            )

            request, metadata = self._interceptor.pre_generate_content(
                request, metadata
            )
            transcoded_request = _BaseGenerativeServiceRestTransport._BaseGenerateContent._get_transcoded_request(
                http_options, request
            )

            body = _BaseGenerativeServiceRestTransport._BaseGenerateContent._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseGenerativeServiceRestTransport._BaseGenerateContent._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1.GenerativeServiceClient.GenerateContent",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
                        "rpcName": "GenerateContent",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = GenerativeServiceRestTransport._GenerateContent._get_response(
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
            resp = generative_service.GenerateContentResponse()
            pb_resp = generative_service.GenerateContentResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_generate_content(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_generate_content_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = (
                        generative_service.GenerateContentResponse.to_json(response)
                    )
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1.GenerativeServiceClient.generate_content",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
                        "rpcName": "GenerateContent",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _StreamGenerateContent(
        _BaseGenerativeServiceRestTransport._BaseStreamGenerateContent,
        GenerativeServiceRestStub,
    ):
        def __hash__(self):
            return hash("GenerativeServiceRestTransport.StreamGenerateContent")

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
                stream=True,
            )
            return response

        def __call__(
            self,
            request: generative_service.GenerateContentRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> rest_streaming.ResponseIterator:
            r"""Call the stream generate content method over HTTP.

            Args:
                request (~.generative_service.GenerateContentRequest):
                    The request object. Request to generate a completion from
                the model.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.generative_service.GenerateContentResponse:
                    Response from the model supporting multiple candidate
                responses.

                Safety ratings and content filtering are reported for
                both prompt in
                ``GenerateContentResponse.prompt_feedback`` and for each
                candidate in ``finish_reason`` and in
                ``safety_ratings``. The API:

                -  Returns either all requested candidates or none of
                   them
                -  Returns no candidates at all only if there was
                   something wrong with the prompt (check
                   ``prompt_feedback``)
                -  Reports feedback on each candidate in
                   ``finish_reason`` and ``safety_ratings``.

            """

            http_options = (
                _BaseGenerativeServiceRestTransport._BaseStreamGenerateContent._get_http_options()
            )

            request, metadata = self._interceptor.pre_stream_generate_content(
                request, metadata
            )
            transcoded_request = _BaseGenerativeServiceRestTransport._BaseStreamGenerateContent._get_transcoded_request(
                http_options, request
            )

            body = _BaseGenerativeServiceRestTransport._BaseStreamGenerateContent._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseGenerativeServiceRestTransport._BaseStreamGenerateContent._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1.GenerativeServiceClient.StreamGenerateContent",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
                        "rpcName": "StreamGenerateContent",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = (
                GenerativeServiceRestTransport._StreamGenerateContent._get_response(
                    self._host,
                    metadata,
                    query_params,
                    self._session,
                    timeout,
                    transcoded_request,
                    body,
                )
            )

            # In case of error, raise the appropriate core_exceptions.GoogleAPICallError exception
            # subclass.
            if response.status_code >= 400:
                raise core_exceptions.from_http_response(response)

            # Return the response
            resp = rest_streaming.ResponseIterator(
                response, generative_service.GenerateContentResponse
            )

            resp = self._interceptor.post_stream_generate_content(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_stream_generate_content_with_metadata(
                resp, response_metadata
            )
            return resp

    @property
    def batch_embed_contents(
        self,
    ) -> Callable[
        [generative_service.BatchEmbedContentsRequest],
        generative_service.BatchEmbedContentsResponse,
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._BatchEmbedContents(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def count_tokens(
        self,
    ) -> Callable[
        [generative_service.CountTokensRequest], generative_service.CountTokensResponse
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._CountTokens(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def embed_content(
        self,
    ) -> Callable[
        [generative_service.EmbedContentRequest],
        generative_service.EmbedContentResponse,
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._EmbedContent(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def generate_content(
        self,
    ) -> Callable[
        [generative_service.GenerateContentRequest],
        generative_service.GenerateContentResponse,
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._GenerateContent(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def stream_generate_content(
        self,
    ) -> Callable[
        [generative_service.GenerateContentRequest],
        generative_service.GenerateContentResponse,
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._StreamGenerateContent(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def cancel_operation(self):
        return self._CancelOperation(self._session, self._host, self._interceptor)  # type: ignore

    class _CancelOperation(
        _BaseGenerativeServiceRestTransport._BaseCancelOperation,
        GenerativeServiceRestStub,
    ):
        def __hash__(self):
            return hash("GenerativeServiceRestTransport.CancelOperation")

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
            request: operations_pb2.CancelOperationRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> None:
            r"""Call the cancel operation method over HTTP.

            Args:
                request (operations_pb2.CancelOperationRequest):
                    The request object for CancelOperation method.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.
            """

            http_options = (
                _BaseGenerativeServiceRestTransport._BaseCancelOperation._get_http_options()
            )

            request, metadata = self._interceptor.pre_cancel_operation(
                request, metadata
            )
            transcoded_request = _BaseGenerativeServiceRestTransport._BaseCancelOperation._get_transcoded_request(
                http_options, request
            )

            body = _BaseGenerativeServiceRestTransport._BaseCancelOperation._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseGenerativeServiceRestTransport._BaseCancelOperation._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1.GenerativeServiceClient.CancelOperation",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
                        "rpcName": "CancelOperation",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = GenerativeServiceRestTransport._CancelOperation._get_response(
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

            return self._interceptor.post_cancel_operation(None)

    @property
    def get_operation(self):
        return self._GetOperation(self._session, self._host, self._interceptor)  # type: ignore

    class _GetOperation(
        _BaseGenerativeServiceRestTransport._BaseGetOperation, GenerativeServiceRestStub
    ):
        def __hash__(self):
            return hash("GenerativeServiceRestTransport.GetOperation")

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
                _BaseGenerativeServiceRestTransport._BaseGetOperation._get_http_options()
            )

            request, metadata = self._interceptor.pre_get_operation(request, metadata)
            transcoded_request = _BaseGenerativeServiceRestTransport._BaseGetOperation._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseGenerativeServiceRestTransport._BaseGetOperation._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1.GenerativeServiceClient.GetOperation",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
                        "rpcName": "GetOperation",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = GenerativeServiceRestTransport._GetOperation._get_response(
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
                    "Received response for google.ai.generativelanguage_v1.GenerativeServiceAsyncClient.GetOperation",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
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
        _BaseGenerativeServiceRestTransport._BaseListOperations,
        GenerativeServiceRestStub,
    ):
        def __hash__(self):
            return hash("GenerativeServiceRestTransport.ListOperations")

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
                _BaseGenerativeServiceRestTransport._BaseListOperations._get_http_options()
            )

            request, metadata = self._interceptor.pre_list_operations(request, metadata)
            transcoded_request = _BaseGenerativeServiceRestTransport._BaseListOperations._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseGenerativeServiceRestTransport._BaseListOperations._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1.GenerativeServiceClient.ListOperations",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
                        "rpcName": "ListOperations",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = GenerativeServiceRestTransport._ListOperations._get_response(
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
                    "Received response for google.ai.generativelanguage_v1.GenerativeServiceAsyncClient.ListOperations",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1.GenerativeService",
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


__all__ = ("GenerativeServiceRestTransport",)
