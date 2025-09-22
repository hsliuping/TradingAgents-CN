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

from google.api_core import gapic_v1, operations_v1, rest_helpers, rest_streaming
from google.api_core import exceptions as core_exceptions
from google.api_core import retry as retries
from google.auth import credentials as ga_credentials  # type: ignore
from google.auth.transport.requests import AuthorizedSession  # type: ignore
from google.longrunning import operations_pb2  # type: ignore
from google.protobuf import empty_pb2  # type: ignore
from google.protobuf import json_format
from requests import __version__ as requests_version

from google.ai.generativelanguage_v1beta3.types import tuned_model as gag_tuned_model
from google.ai.generativelanguage_v1beta3.types import model, model_service
from google.ai.generativelanguage_v1beta3.types import tuned_model

from .base import DEFAULT_CLIENT_INFO as BASE_DEFAULT_CLIENT_INFO
from .rest_base import _BaseModelServiceRestTransport

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


class ModelServiceRestInterceptor:
    """Interceptor for ModelService.

    Interceptors are used to manipulate requests, request metadata, and responses
    in arbitrary ways.
    Example use cases include:
    * Logging
    * Verifying requests according to service or custom semantics
    * Stripping extraneous information from responses

    These use cases and more can be enabled by injecting an
    instance of a custom subclass when constructing the ModelServiceRestTransport.

    .. code-block:: python
        class MyCustomModelServiceInterceptor(ModelServiceRestInterceptor):
            def pre_create_tuned_model(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_create_tuned_model(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_delete_tuned_model(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def pre_get_model(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_get_model(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_get_tuned_model(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_get_tuned_model(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_list_models(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_list_models(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_list_tuned_models(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_list_tuned_models(self, response):
                logging.log(f"Received response: {response}")
                return response

            def pre_update_tuned_model(self, request, metadata):
                logging.log(f"Received request: {request}")
                return request, metadata

            def post_update_tuned_model(self, response):
                logging.log(f"Received response: {response}")
                return response

        transport = ModelServiceRestTransport(interceptor=MyCustomModelServiceInterceptor())
        client = ModelServiceClient(transport=transport)


    """

    def pre_create_tuned_model(
        self,
        request: model_service.CreateTunedModelRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        model_service.CreateTunedModelRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for create_tuned_model

        Override in a subclass to manipulate the request or metadata
        before they are sent to the ModelService server.
        """
        return request, metadata

    def post_create_tuned_model(
        self, response: operations_pb2.Operation
    ) -> operations_pb2.Operation:
        """Post-rpc interceptor for create_tuned_model

        DEPRECATED. Please use the `post_create_tuned_model_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the ModelService server but before
        it is returned to user code. This `post_create_tuned_model` interceptor runs
        before the `post_create_tuned_model_with_metadata` interceptor.
        """
        return response

    def post_create_tuned_model_with_metadata(
        self,
        response: operations_pb2.Operation,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[operations_pb2.Operation, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for create_tuned_model

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the ModelService server but before it is returned to user code.

        We recommend only using this `post_create_tuned_model_with_metadata`
        interceptor in new development instead of the `post_create_tuned_model` interceptor.
        When both interceptors are used, this `post_create_tuned_model_with_metadata` interceptor runs after the
        `post_create_tuned_model` interceptor. The (possibly modified) response returned by
        `post_create_tuned_model` will be passed to
        `post_create_tuned_model_with_metadata`.
        """
        return response, metadata

    def pre_delete_tuned_model(
        self,
        request: model_service.DeleteTunedModelRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        model_service.DeleteTunedModelRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for delete_tuned_model

        Override in a subclass to manipulate the request or metadata
        before they are sent to the ModelService server.
        """
        return request, metadata

    def pre_get_model(
        self,
        request: model_service.GetModelRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[model_service.GetModelRequest, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Pre-rpc interceptor for get_model

        Override in a subclass to manipulate the request or metadata
        before they are sent to the ModelService server.
        """
        return request, metadata

    def post_get_model(self, response: model.Model) -> model.Model:
        """Post-rpc interceptor for get_model

        DEPRECATED. Please use the `post_get_model_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the ModelService server but before
        it is returned to user code. This `post_get_model` interceptor runs
        before the `post_get_model_with_metadata` interceptor.
        """
        return response

    def post_get_model_with_metadata(
        self, response: model.Model, metadata: Sequence[Tuple[str, Union[str, bytes]]]
    ) -> Tuple[model.Model, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for get_model

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the ModelService server but before it is returned to user code.

        We recommend only using this `post_get_model_with_metadata`
        interceptor in new development instead of the `post_get_model` interceptor.
        When both interceptors are used, this `post_get_model_with_metadata` interceptor runs after the
        `post_get_model` interceptor. The (possibly modified) response returned by
        `post_get_model` will be passed to
        `post_get_model_with_metadata`.
        """
        return response, metadata

    def pre_get_tuned_model(
        self,
        request: model_service.GetTunedModelRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        model_service.GetTunedModelRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for get_tuned_model

        Override in a subclass to manipulate the request or metadata
        before they are sent to the ModelService server.
        """
        return request, metadata

    def post_get_tuned_model(
        self, response: tuned_model.TunedModel
    ) -> tuned_model.TunedModel:
        """Post-rpc interceptor for get_tuned_model

        DEPRECATED. Please use the `post_get_tuned_model_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the ModelService server but before
        it is returned to user code. This `post_get_tuned_model` interceptor runs
        before the `post_get_tuned_model_with_metadata` interceptor.
        """
        return response

    def post_get_tuned_model_with_metadata(
        self,
        response: tuned_model.TunedModel,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[tuned_model.TunedModel, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for get_tuned_model

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the ModelService server but before it is returned to user code.

        We recommend only using this `post_get_tuned_model_with_metadata`
        interceptor in new development instead of the `post_get_tuned_model` interceptor.
        When both interceptors are used, this `post_get_tuned_model_with_metadata` interceptor runs after the
        `post_get_tuned_model` interceptor. The (possibly modified) response returned by
        `post_get_tuned_model` will be passed to
        `post_get_tuned_model_with_metadata`.
        """
        return response, metadata

    def pre_list_models(
        self,
        request: model_service.ListModelsRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        model_service.ListModelsRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for list_models

        Override in a subclass to manipulate the request or metadata
        before they are sent to the ModelService server.
        """
        return request, metadata

    def post_list_models(
        self, response: model_service.ListModelsResponse
    ) -> model_service.ListModelsResponse:
        """Post-rpc interceptor for list_models

        DEPRECATED. Please use the `post_list_models_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the ModelService server but before
        it is returned to user code. This `post_list_models` interceptor runs
        before the `post_list_models_with_metadata` interceptor.
        """
        return response

    def post_list_models_with_metadata(
        self,
        response: model_service.ListModelsResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        model_service.ListModelsResponse, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for list_models

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the ModelService server but before it is returned to user code.

        We recommend only using this `post_list_models_with_metadata`
        interceptor in new development instead of the `post_list_models` interceptor.
        When both interceptors are used, this `post_list_models_with_metadata` interceptor runs after the
        `post_list_models` interceptor. The (possibly modified) response returned by
        `post_list_models` will be passed to
        `post_list_models_with_metadata`.
        """
        return response, metadata

    def pre_list_tuned_models(
        self,
        request: model_service.ListTunedModelsRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        model_service.ListTunedModelsRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for list_tuned_models

        Override in a subclass to manipulate the request or metadata
        before they are sent to the ModelService server.
        """
        return request, metadata

    def post_list_tuned_models(
        self, response: model_service.ListTunedModelsResponse
    ) -> model_service.ListTunedModelsResponse:
        """Post-rpc interceptor for list_tuned_models

        DEPRECATED. Please use the `post_list_tuned_models_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the ModelService server but before
        it is returned to user code. This `post_list_tuned_models` interceptor runs
        before the `post_list_tuned_models_with_metadata` interceptor.
        """
        return response

    def post_list_tuned_models_with_metadata(
        self,
        response: model_service.ListTunedModelsResponse,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        model_service.ListTunedModelsResponse, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Post-rpc interceptor for list_tuned_models

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the ModelService server but before it is returned to user code.

        We recommend only using this `post_list_tuned_models_with_metadata`
        interceptor in new development instead of the `post_list_tuned_models` interceptor.
        When both interceptors are used, this `post_list_tuned_models_with_metadata` interceptor runs after the
        `post_list_tuned_models` interceptor. The (possibly modified) response returned by
        `post_list_tuned_models` will be passed to
        `post_list_tuned_models_with_metadata`.
        """
        return response, metadata

    def pre_update_tuned_model(
        self,
        request: model_service.UpdateTunedModelRequest,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[
        model_service.UpdateTunedModelRequest, Sequence[Tuple[str, Union[str, bytes]]]
    ]:
        """Pre-rpc interceptor for update_tuned_model

        Override in a subclass to manipulate the request or metadata
        before they are sent to the ModelService server.
        """
        return request, metadata

    def post_update_tuned_model(
        self, response: gag_tuned_model.TunedModel
    ) -> gag_tuned_model.TunedModel:
        """Post-rpc interceptor for update_tuned_model

        DEPRECATED. Please use the `post_update_tuned_model_with_metadata`
        interceptor instead.

        Override in a subclass to read or manipulate the response
        after it is returned by the ModelService server but before
        it is returned to user code. This `post_update_tuned_model` interceptor runs
        before the `post_update_tuned_model_with_metadata` interceptor.
        """
        return response

    def post_update_tuned_model_with_metadata(
        self,
        response: gag_tuned_model.TunedModel,
        metadata: Sequence[Tuple[str, Union[str, bytes]]],
    ) -> Tuple[gag_tuned_model.TunedModel, Sequence[Tuple[str, Union[str, bytes]]]]:
        """Post-rpc interceptor for update_tuned_model

        Override in a subclass to read or manipulate the response or metadata after it
        is returned by the ModelService server but before it is returned to user code.

        We recommend only using this `post_update_tuned_model_with_metadata`
        interceptor in new development instead of the `post_update_tuned_model` interceptor.
        When both interceptors are used, this `post_update_tuned_model_with_metadata` interceptor runs after the
        `post_update_tuned_model` interceptor. The (possibly modified) response returned by
        `post_update_tuned_model` will be passed to
        `post_update_tuned_model_with_metadata`.
        """
        return response, metadata


@dataclasses.dataclass
class ModelServiceRestStub:
    _session: AuthorizedSession
    _host: str
    _interceptor: ModelServiceRestInterceptor


class ModelServiceRestTransport(_BaseModelServiceRestTransport):
    """REST backend synchronous transport for ModelService.

    Provides methods for getting metadata information about
    Generative Models.

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
        interceptor: Optional[ModelServiceRestInterceptor] = None,
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
        self._operations_client: Optional[operations_v1.AbstractOperationsClient] = None
        if client_cert_source_for_mtls:
            self._session.configure_mtls_channel(client_cert_source_for_mtls)
        self._interceptor = interceptor or ModelServiceRestInterceptor()
        self._prep_wrapped_messages(client_info)

    @property
    def operations_client(self) -> operations_v1.AbstractOperationsClient:
        """Create the client designed to process long-running operations.

        This property caches on the instance; repeated calls return the same
        client.
        """
        # Only create a new client if we do not already have one.
        if self._operations_client is None:
            http_options: Dict[str, List[Dict[str, str]]] = {}

            rest_transport = operations_v1.OperationsRestTransport(
                host=self._host,
                # use the credentials which are saved
                credentials=self._credentials,
                scopes=self._scopes,
                http_options=http_options,
                path_prefix="v1beta3",
            )

            self._operations_client = operations_v1.AbstractOperationsClient(
                transport=rest_transport
            )

        # Return the client from cache.
        return self._operations_client

    class _CreateTunedModel(
        _BaseModelServiceRestTransport._BaseCreateTunedModel, ModelServiceRestStub
    ):
        def __hash__(self):
            return hash("ModelServiceRestTransport.CreateTunedModel")

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
            request: model_service.CreateTunedModelRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> operations_pb2.Operation:
            r"""Call the create tuned model method over HTTP.

            Args:
                request (~.model_service.CreateTunedModelRequest):
                    The request object. Request to create a TunedModel.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.operations_pb2.Operation:
                    This resource represents a
                long-running operation that is the
                result of a network API call.

            """

            http_options = (
                _BaseModelServiceRestTransport._BaseCreateTunedModel._get_http_options()
            )

            request, metadata = self._interceptor.pre_create_tuned_model(
                request, metadata
            )
            transcoded_request = _BaseModelServiceRestTransport._BaseCreateTunedModel._get_transcoded_request(
                http_options, request
            )

            body = _BaseModelServiceRestTransport._BaseCreateTunedModel._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseModelServiceRestTransport._BaseCreateTunedModel._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1beta3.ModelServiceClient.CreateTunedModel",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "CreateTunedModel",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = ModelServiceRestTransport._CreateTunedModel._get_response(
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
            resp = operations_pb2.Operation()
            json_format.Parse(response.content, resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_create_tuned_model(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_create_tuned_model_with_metadata(
                resp, response_metadata
            )
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
                    "Received response for google.ai.generativelanguage_v1beta3.ModelServiceClient.create_tuned_model",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "CreateTunedModel",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _DeleteTunedModel(
        _BaseModelServiceRestTransport._BaseDeleteTunedModel, ModelServiceRestStub
    ):
        def __hash__(self):
            return hash("ModelServiceRestTransport.DeleteTunedModel")

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
            request: model_service.DeleteTunedModelRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ):
            r"""Call the delete tuned model method over HTTP.

            Args:
                request (~.model_service.DeleteTunedModelRequest):
                    The request object. Request to delete a TunedModel.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.
            """

            http_options = (
                _BaseModelServiceRestTransport._BaseDeleteTunedModel._get_http_options()
            )

            request, metadata = self._interceptor.pre_delete_tuned_model(
                request, metadata
            )
            transcoded_request = _BaseModelServiceRestTransport._BaseDeleteTunedModel._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseModelServiceRestTransport._BaseDeleteTunedModel._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1beta3.ModelServiceClient.DeleteTunedModel",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "DeleteTunedModel",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = ModelServiceRestTransport._DeleteTunedModel._get_response(
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

    class _GetModel(_BaseModelServiceRestTransport._BaseGetModel, ModelServiceRestStub):
        def __hash__(self):
            return hash("ModelServiceRestTransport.GetModel")

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
            request: model_service.GetModelRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> model.Model:
            r"""Call the get model method over HTTP.

            Args:
                request (~.model_service.GetModelRequest):
                    The request object. Request for getting information about
                a specific Model.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.model.Model:
                    Information about a Generative
                Language Model.

            """

            http_options = (
                _BaseModelServiceRestTransport._BaseGetModel._get_http_options()
            )

            request, metadata = self._interceptor.pre_get_model(request, metadata)
            transcoded_request = (
                _BaseModelServiceRestTransport._BaseGetModel._get_transcoded_request(
                    http_options, request
                )
            )

            # Jsonify the query params
            query_params = (
                _BaseModelServiceRestTransport._BaseGetModel._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1beta3.ModelServiceClient.GetModel",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "GetModel",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = ModelServiceRestTransport._GetModel._get_response(
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
            resp = model.Model()
            pb_resp = model.Model.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_get_model(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_get_model_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = model.Model.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta3.ModelServiceClient.get_model",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "GetModel",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _GetTunedModel(
        _BaseModelServiceRestTransport._BaseGetTunedModel, ModelServiceRestStub
    ):
        def __hash__(self):
            return hash("ModelServiceRestTransport.GetTunedModel")

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
            request: model_service.GetTunedModelRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> tuned_model.TunedModel:
            r"""Call the get tuned model method over HTTP.

            Args:
                request (~.model_service.GetTunedModelRequest):
                    The request object. Request for getting information about
                a specific Model.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.tuned_model.TunedModel:
                    A fine-tuned model created using
                ModelService.CreateTunedModel.

            """

            http_options = (
                _BaseModelServiceRestTransport._BaseGetTunedModel._get_http_options()
            )

            request, metadata = self._interceptor.pre_get_tuned_model(request, metadata)
            transcoded_request = _BaseModelServiceRestTransport._BaseGetTunedModel._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseModelServiceRestTransport._BaseGetTunedModel._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1beta3.ModelServiceClient.GetTunedModel",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "GetTunedModel",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = ModelServiceRestTransport._GetTunedModel._get_response(
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
            resp = tuned_model.TunedModel()
            pb_resp = tuned_model.TunedModel.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_get_tuned_model(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_get_tuned_model_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = tuned_model.TunedModel.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta3.ModelServiceClient.get_tuned_model",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "GetTunedModel",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _ListModels(
        _BaseModelServiceRestTransport._BaseListModels, ModelServiceRestStub
    ):
        def __hash__(self):
            return hash("ModelServiceRestTransport.ListModels")

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
            request: model_service.ListModelsRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> model_service.ListModelsResponse:
            r"""Call the list models method over HTTP.

            Args:
                request (~.model_service.ListModelsRequest):
                    The request object. Request for listing all Models.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.model_service.ListModelsResponse:
                    Response from ``ListModel`` containing a paginated list
                of Models.

            """

            http_options = (
                _BaseModelServiceRestTransport._BaseListModels._get_http_options()
            )

            request, metadata = self._interceptor.pre_list_models(request, metadata)
            transcoded_request = (
                _BaseModelServiceRestTransport._BaseListModels._get_transcoded_request(
                    http_options, request
                )
            )

            # Jsonify the query params
            query_params = (
                _BaseModelServiceRestTransport._BaseListModels._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1beta3.ModelServiceClient.ListModels",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "ListModels",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = ModelServiceRestTransport._ListModels._get_response(
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
            resp = model_service.ListModelsResponse()
            pb_resp = model_service.ListModelsResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_list_models(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_list_models_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = model_service.ListModelsResponse.to_json(
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
                    "Received response for google.ai.generativelanguage_v1beta3.ModelServiceClient.list_models",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "ListModels",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _ListTunedModels(
        _BaseModelServiceRestTransport._BaseListTunedModels, ModelServiceRestStub
    ):
        def __hash__(self):
            return hash("ModelServiceRestTransport.ListTunedModels")

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
            request: model_service.ListTunedModelsRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> model_service.ListTunedModelsResponse:
            r"""Call the list tuned models method over HTTP.

            Args:
                request (~.model_service.ListTunedModelsRequest):
                    The request object. Request for listing TunedModels.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.model_service.ListTunedModelsResponse:
                    Response from ``ListTunedModels`` containing a paginated
                list of Models.

            """

            http_options = (
                _BaseModelServiceRestTransport._BaseListTunedModels._get_http_options()
            )

            request, metadata = self._interceptor.pre_list_tuned_models(
                request, metadata
            )
            transcoded_request = _BaseModelServiceRestTransport._BaseListTunedModels._get_transcoded_request(
                http_options, request
            )

            # Jsonify the query params
            query_params = _BaseModelServiceRestTransport._BaseListTunedModels._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1beta3.ModelServiceClient.ListTunedModels",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "ListTunedModels",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = ModelServiceRestTransport._ListTunedModels._get_response(
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
            resp = model_service.ListTunedModelsResponse()
            pb_resp = model_service.ListTunedModelsResponse.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_list_tuned_models(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_list_tuned_models_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = model_service.ListTunedModelsResponse.to_json(
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
                    "Received response for google.ai.generativelanguage_v1beta3.ModelServiceClient.list_tuned_models",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "ListTunedModels",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    class _UpdateTunedModel(
        _BaseModelServiceRestTransport._BaseUpdateTunedModel, ModelServiceRestStub
    ):
        def __hash__(self):
            return hash("ModelServiceRestTransport.UpdateTunedModel")

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
            request: model_service.UpdateTunedModelRequest,
            *,
            retry: OptionalRetry = gapic_v1.method.DEFAULT,
            timeout: Optional[float] = None,
            metadata: Sequence[Tuple[str, Union[str, bytes]]] = (),
        ) -> gag_tuned_model.TunedModel:
            r"""Call the update tuned model method over HTTP.

            Args:
                request (~.model_service.UpdateTunedModelRequest):
                    The request object. Request to update a TunedModel.
                retry (google.api_core.retry.Retry): Designation of what errors, if any,
                    should be retried.
                timeout (float): The timeout for this request.
                metadata (Sequence[Tuple[str, Union[str, bytes]]]): Key/value pairs which should be
                    sent along with the request as metadata. Normally, each value must be of type `str`,
                    but for metadata keys ending with the suffix `-bin`, the corresponding values must
                    be of type `bytes`.

            Returns:
                ~.gag_tuned_model.TunedModel:
                    A fine-tuned model created using
                ModelService.CreateTunedModel.

            """

            http_options = (
                _BaseModelServiceRestTransport._BaseUpdateTunedModel._get_http_options()
            )

            request, metadata = self._interceptor.pre_update_tuned_model(
                request, metadata
            )
            transcoded_request = _BaseModelServiceRestTransport._BaseUpdateTunedModel._get_transcoded_request(
                http_options, request
            )

            body = _BaseModelServiceRestTransport._BaseUpdateTunedModel._get_request_body_json(
                transcoded_request
            )

            # Jsonify the query params
            query_params = _BaseModelServiceRestTransport._BaseUpdateTunedModel._get_query_params_json(
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
                    f"Sending request for google.ai.generativelanguage_v1beta3.ModelServiceClient.UpdateTunedModel",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "UpdateTunedModel",
                        "httpRequest": http_request,
                        "metadata": http_request["headers"],
                    },
                )

            # Send the request
            response = ModelServiceRestTransport._UpdateTunedModel._get_response(
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
            resp = gag_tuned_model.TunedModel()
            pb_resp = gag_tuned_model.TunedModel.pb(resp)

            json_format.Parse(response.content, pb_resp, ignore_unknown_fields=True)

            resp = self._interceptor.post_update_tuned_model(resp)
            response_metadata = [(k, str(v)) for k, v in response.headers.items()]
            resp, _ = self._interceptor.post_update_tuned_model_with_metadata(
                resp, response_metadata
            )
            if CLIENT_LOGGING_SUPPORTED and _LOGGER.isEnabledFor(
                logging.DEBUG
            ):  # pragma: NO COVER
                try:
                    response_payload = gag_tuned_model.TunedModel.to_json(response)
                except:
                    response_payload = None
                http_response = {
                    "payload": response_payload,
                    "headers": dict(response.headers),
                    "status": response.status_code,
                }
                _LOGGER.debug(
                    "Received response for google.ai.generativelanguage_v1beta3.ModelServiceClient.update_tuned_model",
                    extra={
                        "serviceName": "google.ai.generativelanguage.v1beta3.ModelService",
                        "rpcName": "UpdateTunedModel",
                        "metadata": http_response["headers"],
                        "httpResponse": http_response,
                    },
                )
            return resp

    @property
    def create_tuned_model(
        self,
    ) -> Callable[[model_service.CreateTunedModelRequest], operations_pb2.Operation]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._CreateTunedModel(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def delete_tuned_model(
        self,
    ) -> Callable[[model_service.DeleteTunedModelRequest], empty_pb2.Empty]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._DeleteTunedModel(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def get_model(self) -> Callable[[model_service.GetModelRequest], model.Model]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._GetModel(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def get_tuned_model(
        self,
    ) -> Callable[[model_service.GetTunedModelRequest], tuned_model.TunedModel]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._GetTunedModel(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def list_models(
        self,
    ) -> Callable[[model_service.ListModelsRequest], model_service.ListModelsResponse]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._ListModels(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def list_tuned_models(
        self,
    ) -> Callable[
        [model_service.ListTunedModelsRequest], model_service.ListTunedModelsResponse
    ]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._ListTunedModels(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def update_tuned_model(
        self,
    ) -> Callable[[model_service.UpdateTunedModelRequest], gag_tuned_model.TunedModel]:
        # The return type is fine, but mypy isn't sophisticated enough to determine what's going on here.
        # In C++ this would require a dynamic_cast
        return self._UpdateTunedModel(self._session, self._host, self._interceptor)  # type: ignore

    @property
    def kind(self) -> str:
        return "rest"

    def close(self):
        self._session.close()


__all__ = ("ModelServiceRestTransport",)
