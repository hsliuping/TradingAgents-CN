# Copyright (c) Alibaba, Inc. and its affiliates.
from urllib.parse import urlencode

import dashscope
from dashscope.api_entities.api_request_data import ApiRequestData
from dashscope.api_entities.http_request import HttpRequest
from dashscope.api_entities.websocket_request import WebSocketRequest
from dashscope.common.constants import (REQUEST_TIMEOUT_KEYWORD,
                                        SERVICE_API_PATH, ApiProtocol,
                                        HTTPMethod)
from dashscope.common.error import InputDataRequired, UnsupportedApiProtocol
from dashscope.common.logging import logger
from dashscope.protocol.websocket import WebsocketStreamingMode
from dashscope.api_entities.encryption import Encryption

def _get_protocol_params(kwargs):
    api_protocol = kwargs.pop('api_protocol', ApiProtocol.HTTPS)
    ws_stream_mode = kwargs.pop('ws_stream_mode', WebsocketStreamingMode.OUT)
    is_binary_input = kwargs.pop('is_binary_input', False)
    http_method = kwargs.pop('http_method', HTTPMethod.POST)
    stream = kwargs.pop('stream', False)
    if not stream and ws_stream_mode == WebsocketStreamingMode.OUT:
        ws_stream_mode = WebsocketStreamingMode.NONE

    async_request = kwargs.pop('async_request', False)
    query = kwargs.pop('query', False)
    headers = kwargs.pop('headers', None)
    request_timeout = kwargs.pop(REQUEST_TIMEOUT_KEYWORD, None)
    form = kwargs.pop('form', None)
    resources = kwargs.pop('resources', None)
    base_address = kwargs.pop('base_address', None)
    flattened_output = kwargs.pop('flattened_output', False)
    extra_url_parameters = kwargs.pop('extra_url_parameters', None)
    return (api_protocol, ws_stream_mode, is_binary_input, http_method, stream,
            async_request, query, headers, request_timeout, form, resources,
            base_address, flattened_output, extra_url_parameters)


def _build_api_request(model: str,
                       input: object,
                       task_group: str,
                       task: str,
                       function: str,
                       api_key: str,
                       is_service=True,
                       **kwargs):
    (api_protocol, ws_stream_mode, is_binary_input, http_method, stream,
     async_request, query, headers, request_timeout, form, resources,
     base_address, flattened_output,
     extra_url_parameters) = _get_protocol_params(kwargs)
    task_id = kwargs.pop('task_id', None)
    enable_encryption = kwargs.pop('enable_encryption', False)
    encryption = None

    if api_protocol in [ApiProtocol.HTTP, ApiProtocol.HTTPS]:
        if base_address is None:
            base_address = dashscope.base_http_api_url
        if not base_address.endswith('/'):
            http_url = base_address + '/'
        else:
            http_url = base_address

        if is_service:
            http_url = http_url + SERVICE_API_PATH + '/'

        if task_group:
            http_url += '%s/' % task_group
        if task:
            http_url += '%s/' % task
        if function:
            http_url += function
        if extra_url_parameters is not None and extra_url_parameters:
            http_url += '?' + urlencode(extra_url_parameters)

        if enable_encryption is True:
            encryption = Encryption()
            encryption.initialize()
            if encryption.is_valid():
                logger.debug('encryption enabled')

        request = HttpRequest(url=http_url,
                              api_key=api_key,
                              http_method=http_method,
                              stream=stream,
                              async_request=async_request,
                              query=query,
                              timeout=request_timeout,
                              task_id=task_id,
                              flattened_output=flattened_output,
                              encryption=encryption)
    elif api_protocol == ApiProtocol.WEBSOCKET:
        if base_address is not None:
            websocket_url = base_address
        else:
            websocket_url = dashscope.base_websocket_api_url
        pre_task_id = kwargs.pop('pre_task_id', None)
        request = WebSocketRequest(url=websocket_url,
                                   api_key=api_key,
                                   stream=stream,
                                   ws_stream_mode=ws_stream_mode,
                                   is_binary_input=is_binary_input,
                                   timeout=request_timeout,
                                   flattened_output=flattened_output,
                                   pre_task_id=pre_task_id)
    else:
        raise UnsupportedApiProtocol(
            'Unsupported protocol: %s, support [http, https, websocket]' %
            api_protocol)

    if headers is not None:
        request.add_headers(headers=headers)

    if input is None and form is None:
        raise InputDataRequired('There is no input data and form data')

    if encryption and encryption.is_valid():
        input = encryption.encrypt(input)

    request_data = ApiRequestData(model,
                                  task_group=task_group,
                                  task=task,
                                  function=function,
                                  input=input,
                                  form=form,
                                  is_binary_input=is_binary_input,
                                  api_protocol=api_protocol)
    request_data.add_resources(resources)
    request_data.add_parameters(**kwargs)
    request.data = request_data
    return request
