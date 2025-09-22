# Copyright (c) Alibaba, Inc. and its affiliates.

import json
from http import HTTPStatus
from typing import Optional

import aiohttp
import requests

from dashscope.api_entities.base_request import AioBaseRequest
from dashscope.api_entities.dashscope_response import DashScopeAPIResponse
from dashscope.common.constants import (DEFAULT_REQUEST_TIMEOUT_SECONDS,
                                        SSE_CONTENT_TYPE, HTTPMethod)
from dashscope.common.error import UnsupportedHTTPMethod
from dashscope.common.logging import logger
from dashscope.common.utils import (_handle_aio_stream,
                                    _handle_aiohttp_failed_response,
                                    _handle_http_failed_response,
                                    _handle_stream)
from dashscope.api_entities.encryption import Encryption


class HttpRequest(AioBaseRequest):
    def __init__(self,
                 url: str,
                 api_key: str,
                 http_method: str,
                 stream: bool = True,
                 async_request: bool = False,
                 query: bool = False,
                 timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
                 task_id: str = None,
                 flattened_output: bool = False,
                 encryption: Optional[Encryption] = None) -> None:
        """HttpSSERequest, processing http server sent event stream.

        Args:
            url (str): The request url.
            api_key (str): The api key.
            method (str): The http method(GET|POST).
            stream (bool, optional): Is stream request. Defaults to True.
            timeout (int, optional): Total request timeout.
                Defaults to DEFAULT_REQUEST_TIMEOUT_SECONDS.
        """

        super().__init__()
        self.url = url
        self.flattened_output = flattened_output
        self.async_request = async_request
        self.encryption = encryption
        self.headers = {
            'Accept': 'application/json',
            'Authorization': 'Bearer %s' % api_key,
            **self.headers,
        }

        if encryption and encryption.is_valid():
            self.headers = {
                "X-DashScope-EncryptionKey": json.dumps({
                    "public_key_id": encryption.get_pub_key_id(),
                    "encrypt_key": encryption.get_encrypted_aes_key_str(),
                    "iv": encryption.get_base64_iv_str()
                }),
                **self.headers,
            }

        self.query = query
        if self.async_request and self.query is False:
            self.headers = {
                'X-DashScope-Async': 'enable',
                **self.headers,
            }
        self.method = http_method
        if self.method == HTTPMethod.POST:
            self.headers['Content-Type'] = 'application/json'

        self.stream = stream
        if self.stream:
            self.headers['Accept'] = SSE_CONTENT_TYPE
            self.headers['X-Accel-Buffering'] = 'no'
            self.headers['X-DashScope-SSE'] = 'enable'
        if self.query:
            self.url = self.url.replace('api', 'api-task')
            self.url += '%s' % task_id
        if timeout is None:
            self.timeout = DEFAULT_REQUEST_TIMEOUT_SECONDS
        else:
            self.timeout = timeout

    def add_header(self, key, value):
        self.headers[key] = value

    def add_headers(self, headers):
        self.headers = {**self.headers, **headers}

    def call(self):
        response = self._handle_request()
        if self.stream:
            return (item for item in response)
        else:
            output = next(response)
            try:
                next(response)
            except StopIteration:
                pass
            return output

    async def aio_call(self):
        response = self._handle_aio_request()
        if self.stream:
            return (item async for item in response)
        else:
            result = await response.__anext__()
            try:
                await response.__anext__()
            except StopAsyncIteration:
                pass
            return result

    async def _handle_aio_request(self):
        try:
            async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    headers=self.headers) as session:
                logger.debug('Starting request: %s' % self.url)
                if self.method == HTTPMethod.POST:
                    is_form, obj = self.data.get_aiohttp_payload()
                    if is_form:
                        headers = {**self.headers, **obj.headers}
                        response = await session.post(url=self.url,
                                                      data=obj,
                                                      headers=headers)
                    else:
                        response = await session.request('POST',
                                                         url=self.url,
                                                         json=obj,
                                                         headers=self.headers)
                elif self.method == HTTPMethod.GET:
                    response = await session.get(url=self.url,
                                                 params=self.data.parameters,
                                                 headers=self.headers)
                else:
                    raise UnsupportedHTTPMethod('Unsupported http method: %s' %
                                                self.method)
                logger.debug('Response returned: %s' % self.url)
                async with response:
                    async for rsp in self._handle_aio_response(response):
                        yield rsp
        except aiohttp.ClientConnectorError as e:
            logger.error(e)
            raise e
        except BaseException as e:
            logger.error(e)
            raise e

    async def _handle_aio_response(self, response: aiohttp.ClientResponse):
        request_id = ''
        if (response.status == HTTPStatus.OK and self.stream
                and SSE_CONTENT_TYPE in response.content_type):
            async for is_error, status_code, data in _handle_aio_stream(
                    response):
                try:
                    output = None
                    usage = None
                    msg = json.loads(data)
                    if not is_error:
                        if 'output' in msg:
                            output = msg['output']
                        if 'usage' in msg:
                            usage = msg['usage']
                    if 'request_id' in msg:
                        request_id = msg['request_id']
                except json.JSONDecodeError:
                    yield DashScopeAPIResponse(
                        request_id=request_id,
                        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                        code='Unknown',
                        message=data)
                    continue
                if is_error:
                    yield DashScopeAPIResponse(request_id=request_id,
                                               status_code=status_code,
                                               code=msg['code'],
                                               message=msg['message'])
                else:
                    if self.encryption and self.encryption.is_valid():
                        output = self.encryption.decrypt(output)
                    yield DashScopeAPIResponse(request_id=request_id,
                                               status_code=HTTPStatus.OK,
                                               output=output,
                                               usage=usage)
        elif (response.status == HTTPStatus.OK
              and 'multipart' in response.content_type):
            reader = aiohttp.MultipartReader.from_response(response)
            output = {}
            while True:
                part = await reader.next()
                if part is None:
                    break
                output[part.name] = await part.read()
            if 'request_id' in output:
                request_id = output['request_id']
            if self.encryption and self.encryption.is_valid():
                output = self.encryption.decrypt(output)
            yield DashScopeAPIResponse(request_id=request_id,
                                       status_code=HTTPStatus.OK,
                                       output=output)
        elif response.status == HTTPStatus.OK:
            json_content = await response.json()
            output = None
            usage = None
            if 'output' in json_content and json_content['output'] is not None:
                output = json_content['output']
            if 'usage' in json_content:
                usage = json_content['usage']
            if 'request_id' in json_content:
                request_id = json_content['request_id']
            if self.encryption and self.encryption.is_valid():
                output = self.encryption.decrypt(output)
            yield DashScopeAPIResponse(request_id=request_id,
                                       status_code=HTTPStatus.OK,
                                       output=output,
                                       usage=usage)
        else:
            yield await _handle_aiohttp_failed_response(response)

    def _handle_response(self, response: requests.Response):
        request_id = ''
        if (response.status_code == HTTPStatus.OK and self.stream
                and SSE_CONTENT_TYPE in response.headers.get(
                    'content-type', '')):
            for is_error, status_code, event in _handle_stream(response):
                try:
                    data = event.data
                    output = None
                    usage = None
                    msg = json.loads(data)
                    logger.debug('Stream message: %s' % msg)
                    if not is_error:
                        if 'output' in msg:
                            output = msg['output']
                        if 'usage' in msg:
                            usage = msg['usage']
                    if 'request_id' in msg:
                        request_id = msg['request_id']
                except json.JSONDecodeError:
                    yield DashScopeAPIResponse(
                        request_id=request_id,
                        status_code=HTTPStatus.BAD_REQUEST,
                        output=None,
                        code='Unknown',
                        message=data)
                    continue
                if is_error:
                    yield DashScopeAPIResponse(
                        request_id=request_id,
                        status_code=status_code,
                        output=None,
                        code=msg['code']
                        if 'code' in msg else None,  # noqa E501
                        message=msg['message']
                        if 'message' in msg else None)  # noqa E501
                else:
                    if self.flattened_output:
                        yield msg
                    else:
                        if self.encryption and self.encryption.is_valid():
                            output = self.encryption.decrypt(output)
                        yield DashScopeAPIResponse(request_id=request_id,
                                                   status_code=HTTPStatus.OK,
                                                   output=output,
                                                   usage=usage)
        elif response.status_code == HTTPStatus.OK:
            json_content = response.json()
            logger.debug('Response: %s' % json_content)
            output = None
            usage = None
            if 'task_id' in json_content:
                output = {'task_id': json_content['task_id']}
            if 'output' in json_content:
                output = json_content['output']
            if 'usage' in json_content:
                usage = json_content['usage']
            if 'request_id' in json_content:
                request_id = json_content['request_id']
            if self.flattened_output:
                yield json_content
            else:
                if self.encryption and self.encryption.is_valid():
                    output = self.encryption.decrypt(output)
                yield DashScopeAPIResponse(request_id=request_id,
                                           status_code=HTTPStatus.OK,
                                           output=output,
                                           usage=usage)
        else:
            yield _handle_http_failed_response(response)

    def _handle_request(self):
        try:
            with requests.Session() as session:
                if self.method == HTTPMethod.POST:
                    is_form, form, obj = self.data.get_http_payload()
                    if is_form:
                        headers = {**self.headers}
                        headers.pop('Content-Type')
                        response = session.post(url=self.url,
                                                data=obj,
                                                files=form,
                                                headers=headers,
                                                timeout=self.timeout)
                    else:
                        logger.debug('Request body: %s' % obj)
                        response = session.post(url=self.url,
                                                stream=self.stream,
                                                json=obj,
                                                headers={**self.headers},
                                                timeout=self.timeout)
                elif self.method == HTTPMethod.GET:
                    response = session.get(url=self.url,
                                           params=self.data.parameters,
                                           headers=self.headers,
                                           timeout=self.timeout)
                else:
                    raise UnsupportedHTTPMethod('Unsupported http method: %s' %
                                                self.method)
                for rsp in self._handle_response(response):
                    yield rsp
        except BaseException as e:
            logger.error(e)
            raise e
