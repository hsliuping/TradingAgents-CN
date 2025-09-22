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

from google.ai.generativelanguage_v1beta3.types import text_service

from .base import DEFAULT_CLIENT_INFO as BASE_DEFAULT_CLIENT_INFO
from .rest_base import _BaseTextServiceRestTransport

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


class TextServiceRestInterceptor:
    """Interceptor for TextService.

    Interceptors are used to manipulate requests, request metadata, and responses
    in arbitrary ways.
    Example use cases include:
    * Logging
    * Verifying requests according to service or custom semantics
    * Stripping extraneous information from responses

    These use cases and more can be enabled by injecting an
    instance of a custom subclass when constructing the TextServiceRestTransport.

    .. code-block:: python
        class MyCustomTextServiceInterceptor(TextServiceRestInterceptor):
            def pre_batch_embed_text(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_batch_embed_text(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_count_text_tokens(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_count_text_tokens(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_embed_text(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_embed_text(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_generate_text(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_generate_text(self, response):
                logging.log(f"Received response: {response}")
                return response

        transport = TextServiceRestTransport(interceptor=MyCustomTextServiceInterceptor())
        client = TextServiceClient(transport=transport)


    """

    def pre_batch_embed_text(
        self,
        request: text_service.BatchEmbedTextRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        text_service.BatchEmbedTextRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for batch_embed_text

        Override in a subclass to manipulate the request or metadata
        before they are sent to the TextService server.
        """
        return request, metadata

    def post_batch_embed_text(
        self, response: text_service.BatchEmbedTextResponse
    ) -> text_service.BatchEmbedTextResponse:
        """Post-rpc interceptor for batch_embed_text

        DEPRECATED. Please use the `post_batch_embed_text_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the TextService server but before
        it is returned to user code. This `post_batch_embed_text` interceptor runs
        before the `post_batch_embed_text_with_metadata` interceptor.
        """
        return response

    def post_batch_embed_text_with_metadata(
        self,
        response: text_service.BatchEmbedTextResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        text_service.BatchEmbedTextResponse, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for batch_embed_text

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the TextService server but before it is returned to user code.

        We recommend only using this `post_batch_embed_text_with_metadata`
        interceptor in new development instead of the `post_batch_embed_text` interceptor.
        When both interceptors are used, this `post_batch_embed_text_with_metadata` interceptor runs after the
        `post_batch_embed_text` interceptor. The (possibly modified) response returned by
        `post_batch_embed_text` will be passed to
        `post_batch_embed_text_with_metadata`.
        """
        return response, metadata

    def pre_count_text_tokens(
        self,
        request: text_service.CountTextTokensRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        text_service.CountTextTokensRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for count_text_tokens

        Override in a subclass to manipulate the request or metadata
        before they are sent to the TextService server.
        """
        return request, metadata

    def post_count_text_tokens(
        self, response: text_service.CountTextTokensResponse
    ) -> text_service.CountTextTokensResponse:
        """Post-rpc interceptor for count_text_tokens

        DEPRECATED. Please use the `post_count_text_tokens_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the TextService server but before
        it is returned to user code. This `post_count_text_tokens` interceptor runs
        before the `post_count_text_tokens_with_metadata` interceptor.
        """
        return response

    def post_count_text_tokens_with_metadata(
        self,
        response: text_service.CountTextTokensResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        text_service.CountTextTokensResponse, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for count_text_tokens

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the TextService server but before it is returned to user code.

        We recommend only using this `post_count_text_tokens_with_metadata`
        interceptor in new development instead of the `post_count_text_tokens` interceptor.
        When both interceptors are used, this `post_count_text_tokens_with_metadata` interceptor runs after the
        `post_count_text_tokens` interceptor. The (possibly modified) response returned by
        `post_count_text_tokens` will be passed to
        `post_count_text_tokens_with_metadata`.
        """
        return response, metadata

    def pre_embed_text(
        self,
        request: text_service.EmbedTextRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[text_service.EmbedTextRequest, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Pre-rpc interceptor for embed_text

        Override in a subclass to manipulate the request or metadata
        before they are sent to the TextService server.
        """
        return request, metadata

    def post_embed_text(
        self, response: text_service.EmbedTextResponse
    ) -> text_service.EmbedTextResponse:
        """Post-rpc interceptor for embed_text

        DEPRECATED. Please use the `post_embed_text_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the TextService server but before
        it is returned to user code. This `post_embed_text` interceptor runs
        before the `post_embed_text_with_metadata` interceptor.
        """
        return response

    def post_embed_text_with_metadata(
        self,
        response: text_service.EmbedTextResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[text_service.EmbedTextResponse, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for embed_text

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the TextService server but before it is returned to user code.

        We recommend only using this `post_embed_text_with_metadata`
        interceptor in new development instead of the `post_embed_text` interceptor.
        When both interceptors are used, this `post_embed_text_with_metadata` interceptor runs after the
        `post_embed_text` interceptor. The (possibly modified) response returned by
        `post_embed_text` will be passed to
        `post_embed_text_with_metadata`.
        """
        return response, metadata

    def pre_generate_text(
        self,
        request: text_service.GenerateTextRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        text_service.GenerateTextRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for generate_text

        Override in a subclass to manipulate the request or metadata
        before they are sent to the TextService server.
        """
        return request, metadata

    def post_generate_text(
        self, response: text_service.GenerateTextResponse
    ) -> text_service.GenerateTextResponse:
        """Post-rpc interceptor for generate_text

        DEPRECATED. Please use the `post_generate_text_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the TextService server but before
        it is returned to user code. This `post_generate_text` interceptor runs
        before the `post_generate_text_with_metadata` interceptor.
        """
        return response

    def post_generate_text_with_metadata(
        self,
        response: text_service.GenerateTextResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        text_service.GenerateTextResponse, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for generate_text

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the TextService server but before it is returned to user code.

        We recommend only using this `post_generate_text_with_metadata`
        interceptor in new development instead of the `post_generate_text` interceptor.
        When both interceptors are used, this `post_generate_text_with_metadata` interceptor runs after the
        `post_generate_text` interceptor. The (possibly modified) response returned by
        `post_generate_text` will be passed to
        `post_generate_text_with_metadata`.
        """
        return response, metadata


@dataclasses.dataclass
class TextServiceRestStub:
    _session: AuthorizedSession
    _host: str
    _interceptor: TextServiceRestInterceptor


class TextServiceRestTransport(_BaseTextServiceRestTransport):
    """REST backend synchronous transport for TextService.

    API for using Generative Language Models (GLMs) trained to
    generate text.
    Also known as Large Language Models (LLM)s, these generate text
    given an input prompt from the user.

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
        interceptor: Optional[TextServiceRestInterceptor] = None,
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
        self._interceptor = interceptor or TextServiceRestInterceptor()
        self._prep_wrapped_messages(client_info)

    class _BatchEmbedText(
        _BaseTextServiceRestTransport._BaseBatchEmbedText, TextServiceRestStub
    ):
        def __hash__(self):
            return hash("TextServiceRestTransport.BatchEmbedText")

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
            request: text_service.BatchEmbedTextRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> text_service.BatchEmbedTextResponse:
            r"""Call the batch embed text method over HTTP.

            Args:
                request (~.text_service.BatchEmbedTextRequest):
                    The request object. Batch request to get a text embedding
                from the model.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.text_service.BatchEmbedTextResponse:
                    The response to a EmbedTextRequest.
            """

            http_options = (
                _BaseTextServiceRestTransport._BaseBatchEmbedText._get_http_options()
            )

            request, metadata = self._interceptor.pre_batch_embed_text(
                request, metadata
            )
            transcoded_request = _BaseTextServiceRestTransport._BaseBatchEmbedText._get_transcoded_request(
                http_options, request
            )

            body = _BaseTextServiceRestTransport._BaseBatchEmbedText._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseTextServiceRestTransport._BaseBatchEmbedText._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1beta3.TextServiceClient.BatchEmbedText",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.TextService",
                        "rpcName": "BatchEmbedText",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = TextServiceRestTransport._BatchEmbedText._get_response(
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
            resp = text_service.BatchEmbedTextResponse()
            pb_resp = text_service.BatchEmbedTextResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_batch_embed_text(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_batch_embed_text_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = text_service.BatchEmbedTextResponse.to_json(
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
                    "Received response for google.ai.generativelanguage_v1beta3.TextServiceClient.batch_embed_text",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.TextService",
                        "rpcName": "BatchEmbedText",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _CountTextTokens(
        _BaseTextServiceRestTransport._BaseCountTextTokens, TextServiceRestStub
    ):
        def __hash__(self):
            return hash("TextServiceRestTransport.CountTextTokens")

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
            request: text_service.CountTextTokensRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> text_service.CountTextTokensResponse:
            r"""Call the count text tokens method over HTTP.

            Args:
                request (~.text_service.CountTextTokensRequest):
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
                ~.text_service.CountTextTokensResponse:
                    A response from ``CountTextTokens``.

                It returns the model's ``token_count`` for the
                ``prompt``.

            """

            http_options = (
                _BaseTextServiceRestTransport._BaseCountTextTokens._get_http_options()
            )

            request, metadata = self._interceptor.pre_count_text_tokens(
                request, metadata
            )
            transcoded_request = _BaseTextServiceRestTransport._BaseCountTextTokens._get_transcoded_request(
                http_options, request
            )

            body = _BaseTextServiceRestTransport._BaseCountTextTokens._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseTextServiceRestTransport._BaseCountTextTokens._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1beta3.TextServiceClient.CountTextTokens",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.TextService",
                        "rpcName": "CountTextTokens",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = TextServiceRestTransport._CountTextTokens._get_response(
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
            resp = text_service.CountTextTokensResponse()
            pb_resp = text_service.CountTextTokensResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_count_text_tokens(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_count_text_tokens_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = text_service.CountTextTokensResponse.to_json(
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
                    "Received response for google.ai.generativelanguage_v1beta3.TextServiceClient.count_text_tokens",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.TextService",
                        "rpcName": "CountTextTokens",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _EmbedText(_BaseTextServiceRestTransport._BaseEmbedText, TextServiceRestStub):
        def __hash__(self):
            return hash("TextServiceRestTransport.EmbedText")

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
            request: text_service.EmbedTextRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> text_service.EmbedTextResponse:
            r"""Call the embed text method over HTTP.

            Args:
                request (~.text_service.EmbedTextRequest):
                    The request object. Request to get a text embedding from
                the model.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.text_service.EmbedTextResponse:
                    The response to a EmbedTextRequest.
            """

            http_options = (
                _BaseTextServiceRestTransport._BaseEmbedText._get_http_options()
            )

            request, metadata = self._interceptor.pre_embed_text(request, metadata)
            transcoded_request = (
                _BaseTextServiceRestTransport._BaseEmbedText._get_transcoded_request(
                    http_options, request
                )
            )

            body = _BaseTextServiceRestTransport._BaseEmbedText._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = (
                _BaseTextServiceRestTransport._BaseEmbedText._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1beta3.TextServiceClient.EmbedText",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.TextService",
                        "rpcName": "EmbedText",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = TextServiceRestTransport._EmbedText._get_response(
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
            resp = text_service.EmbedTextResponse()
            pb_resp = text_service.EmbedTextResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_embed_text(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_embed_text_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = text_service.EmbedTextResponse.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta3.TextServiceClient.embed_text",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.TextService",
                        "rpcName": "EmbedText",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _GenerateText(
        _BaseTextServiceRestTransport._BaseGenerateText, TextServiceRestStub
    ):
        def __hash__(self):
            return hash("TextServiceRestTransport.GenerateText")

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
            request: text_service.GenerateTextRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> text_service.GenerateTextResponse:
            r"""Call the generate text method over HTTP.

            Args:
                request (~.text_service.GenerateTextRequest):
                    The request object. Request to generate a text completion
                response from the model.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.text_service.GenerateTextResponse:
                    The response from the model,
                including candidate completions.

            """

            http_options = (
                _BaseTextServiceRestTransport._BaseGenerateText._get_http_options()
            )

            request, metadata = self._interceptor.pre_generate_text(request, metadata)
            transcoded_request = (
                _BaseTextServiceRestTransport._BaseGenerateText._get_transcoded_request(
                    http_options, request
                )
            )

            body = (
                _BaseTextServiceRestTransport._BaseGenerateText._get_request_body_json(
                    transcoded_request
                )
            )

            # Jsonify the query params
            query_params = (
                _BaseTextServiceRestTransport._BaseGenerateText._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1beta3.TextServiceClient.GenerateText",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.TextService",
                        "rpcName": "GenerateText",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = TextServiceRestTransport._GenerateText._get_response(
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
            resp = text_service.GenerateTextResponse()
            pb_resp = text_service.GenerateTextResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_generate_text(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_generate_text_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = text_service.GenerateTextResponse.to_json(
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
                    "Received response for google.ai.generativelanguage_v1beta3.TextServiceClient.generate_text",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.TextService",
                        "rpcName": "GenerateText",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    @property
    def batch_embed_text(
        self,
    ) -> Callable[
        [text_service.BatchEmbedTextRequest], text_service.BatchEmbedTextResponse
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._BatchEmbedText(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def count_text_tokens(
        self,
    ) -> Callable[
        [text_service.CountTextTokensRequest], text_service.CountTextTokensResponse
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._CountTextTokens(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def embed_text(
        self,
    ) -> Callable[[text_service.EmbedTextRequest], text_service.EmbedTextResponse]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._EmbedText(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def generate_text(
        self,
    ) -> Callable[
        [text_service.GenerateTextRequest], text_service.GenerateTextResponse
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._GenerateText(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def kind(self) -> str:
        return "rest"

    def close(self):
        self._session.close()


__all__ = ("TextServiceRestTransport",)
