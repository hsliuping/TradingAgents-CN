# Copyright (c) Alibaba, Inc. and its affiliates.

import asyncio
import json
import uuid
from http import HTTPStatus
from typing import Tuple, Union

import aiohttp

from dashscope.api_entities.base_request import AioBaseRequest
from dashscope.api_entities.dashscope_response import DashScopeAPIResponse
from dashscope.common.constants import (DEFAULT_REQUEST_TIMEOUT_SECONDS,
                                        SERVICE_503_MESSAGE,
                                        WEBSOCKET_ERROR_CODE)
from dashscope.common.error import (RequestFailure, UnexpectedMessageReceived,
                                    UnknownMessageReceived)
from dashscope.common.logging import logger
from dashscope.common.utils import async_to_sync
from dashscope.protocol.websocket import (ACTION_KEY, ERROR_MESSAGE,
                                          ERROR_NAME, EVENT_KEY, HEADER,
                                          TASK_ID, ActionType, EventType,
                                          WebsocketStreamingMode)


class WebSocketRequest(AioBaseRequest):
    def __init__(
        self,
        url: str,
        api_key: str,
        stream: bool = True,
        ws_stream_mode: str = WebsocketStreamingMode.OUT,
        is_binary_input: bool = False,
        timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        flattened_output: bool = False,
        pre_task_id=None,
    ) -> None:
        super().__init__()
        """HttpRequest.

        Args:
            url (str): The request url.
            api_key (str): The api key.
            method (str): The http method(GET|POST).
            stream (bool, optional): Is stream request. Defaults to False.
            timeout (int, optional): Total request timeout.
                Defaults to DEFAULT_REQUEST_TIMEOUT_SECONDS.
        """
        self.url = url
        self.stream = stream
        self.flattened_output = flattened_output
        if timeout is None:
            self.timeout = DEFAULT_REQUEST_TIMEOUT_SECONDS
        else:
            self.timeout = timeout
        self.ws_stream_mode = ws_stream_mode
        self.is_binary_input = is_binary_input

        self.headers = {
            'Authorization': 'bearer %s' % api_key,
            **self.headers,
        }

        self.task_headers = {
            'streaming': self.ws_stream_mode,
        }
        self.pre_task_id = pre_task_id

    def add_headers(self, headers):
        self.headers = {**self.headers, **headers}

    def call(self):
        response = async_to_sync(self.connection_handler())
        if self.stream:
            return (item for item in response)
        else:
            output = next(response)
            try:
                next(response)
            except StopIteration:
                pass
            return output

    async def close(self):
        if self.ws is not None and not self.ws.closed:
            await self.ws.close()

    async def aio_call(self):
        response = self.connection_handler()
        if self.stream:
            return (item async for item in response)
        else:
            result = await response.__anext__()
            try:
                await response.__anext__()
            except StopAsyncIteration:
                pass
            return result

    async def connection_handler(self):
        try:
            task_id = None
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(
                    total=self.timeout)) as session:
                async with session.ws_connect(self.url,
                                              headers=self.headers,
                                              heartbeat=6000) as ws:
                    await self._start_task(ws)  # send start task action.
                    task_id = self.task_headers['task_id']
                    await self._wait_for_task_started(
                        ws)  # wait for task started event. # noqa E501
                    if self.ws_stream_mode == WebsocketStreamingMode.NONE:
                        if self.is_binary_input:  # send the binary package
                            data = self.data.get_batch_binary_data()
                            await ws.send_bytes(list(data.values())[0])
                        is_binary, result = await self._receive_batch_data_task(  # noqa E501
                            ws)
                        # do not need send finished task message.
                        yield self._to_DashScopeAPIResponse(
                            task_id, is_binary, result)
                    elif self.ws_stream_mode == WebsocketStreamingMode.IN:
                        # server is in, we send streaming out.
                        await self._send_continue_task_data(ws)
                        is_binary, result = await self._receive_batch_data_task(  # noqa E501
                            ws)
                        # do not need send finished task message.
                        yield self._to_DashScopeAPIResponse(
                            task_id, is_binary, result)
                    elif self.ws_stream_mode == WebsocketStreamingMode.OUT:
                        # we send batch data, server streaming output data.
                        if self.is_binary_input:  # send only binary package.
                            data = self.data.get_batch_binary_data()
                            await ws.send_bytes(list(data.values())[0])
                        async for is_binary, message in self._receive_streaming_data_task(  # noqa E501
                                ws):
                            yield self._to_DashScopeAPIResponse(
                                task_id, is_binary, message)
                    else:  # duplex mode
                        asyncio.create_task(self._send_continue_task_data(ws))
                        async for is_binary, message in self._receive_streaming_data_task(  # noqa E501
                                ws):
                            yield self._to_DashScopeAPIResponse(
                                task_id, is_binary, message)
        except RequestFailure as e:
            yield DashScopeAPIResponse(request_id=e.request_id,
                                       status_code=e.http_code,
                                       output=None,
                                       code=e.name,
                                       message=e.message)
        except aiohttp.ClientConnectorError as e:
            logger.exception(e)
            yield DashScopeAPIResponse(request_id='',
                                       status_code=-1,
                                       code='ClientConnectorError',
                                       message=str(e))
        except aiohttp.WSServerHandshakeError as e:
            code = e.status
            msg = e.message
            if e.status in [HTTPStatus.FORBIDDEN, HTTPStatus.UNAUTHORIZED]:
                msg = 'Unauthorized, your api-key is invalid!'
            elif e.status == HTTPStatus.SERVICE_UNAVAILABLE:
                msg = SERVICE_503_MESSAGE
            else:
                pass
            yield DashScopeAPIResponse(request_id=task_id,
                                       status_code=code,
                                       code=code,
                                       message=msg)
        except BaseException as e:
            logger.exception(e)
            yield DashScopeAPIResponse(request_id='',
                                       status_code=-1,
                                       code='Unknown',
                                       message='Error type: %s, message: %s' %
                                       (type(e), e))

    def _to_DashScopeAPIResponse(self, task_id, is_binary, result):
        if is_binary:
            return DashScopeAPIResponse(request_id=task_id,
                                        status_code=HTTPStatus.OK,
                                        output=result)
        else:
            # get output and usage.
            output = {}
            usage = {}
            if 'output' in result:
                output = result['output']
            if 'usage' in result:
                usage = result['usage']
            return DashScopeAPIResponse(request_id=task_id,
                                        status_code=HTTPStatus.OK,
                                        output=output,
                                        usage=usage)

    async def _receive_streaming_data_task(self, ws):
        # check if request stream data, re return an iterator,
        # otherwise we collect data and return user.
        # no matter what, the response is streaming
        is_binary_output = False
        while True:
            msg = await ws.receive()
            await self._check_websocket_unexpected_message(msg)
            if msg.type == aiohttp.WSMsgType.TEXT:
                msg_json = msg.json()
                logger.debug('Receive %s event' % msg_json[HEADER][EVENT_KEY])
                if msg_json[HEADER][EVENT_KEY] == EventType.GENERATED:
                    payload = msg_json['payload']
                    yield False, payload
                elif msg_json[HEADER][EVENT_KEY] == EventType.FINISHED:
                    payload = None
                    if 'payload' in msg_json:
                        payload = msg_json['payload']
                    logger.debug(payload)
                    if payload:
                        yield False, payload
                    else:
                        if not self.stream:
                            if is_binary_output:
                                yield True, payload
                            else:
                                yield False, payload
                    break
                elif msg_json[HEADER][EVENT_KEY] == EventType.FAILED:
                    self._on_failed(msg_json)
                else:
                    error = 'Receive unknown message: %s' % msg_json
                    logger.error(error)
                    raise UnknownMessageReceived(error)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                is_binary_output = True
                yield True, msg.data

    def _on_failed(self, details):
        error = RequestFailure(request_id=details[HEADER][TASK_ID],
                               http_code=WEBSOCKET_ERROR_CODE,
                               name=details[HEADER][ERROR_NAME],
                               message=details[HEADER][ERROR_MESSAGE])
        logger.error(error)
        raise error

    async def _start_task(self, ws):
        if self.pre_task_id is not None:
            self.task_headers['task_id'] = self.pre_task_id
        else:
            self.task_headers['task_id'] = uuid.uuid4().hex  # create task id.
        task_header = {**self.task_headers, ACTION_KEY: ActionType.START}
        # for binary data, the start action has no input, only parameters.
        start_data = self.data.get_websocket_start_data()
        message = self._build_up_message(task_header, start_data)
        logger.debug('Send start task: {}'.format(message))
        await ws.send_str(message)

    async def _send_finished_task(self, ws):
        task_header = {**self.task_headers, ACTION_KEY: ActionType.FINISHED}
        payload = {'input': {}}
        message = self._build_up_message(task_header, payload)
        logger.debug('Send finish task: {}'.format(message))
        await ws.send_str(message)

    async def _send_continue_task_data(self, ws):
        headers = {
            'task_id': self.task_headers['task_id'],
            'action': 'continue-task'
        }
        for input in self.data.get_websocket_continue_data():
            if self.is_binary_input:
                if len(input) > 0:
                    if isinstance(input, bytes):
                        await ws.send_bytes(input)
                        logger.debug(
                            'Send continue task with bytes: {}'.format(
                                len(input)))
                    else:
                        await ws.send_bytes(list(input.values())[0])
                        logger.debug(
                            'Send continue task with list[byte]: {}'.format(
                                len(input)))
            else:
                if len(input) > 0:
                    message = self._build_up_message(headers=headers,
                                                     payload=input)
                    logger.debug('Send continue task: {}'.format(message))
                    await ws.send_str(message)
            await asyncio.sleep(0.000001)

        # data send completed, and send task completed.
        await self._send_finished_task(ws)

    async def _receive_batch_data_task(self,
                                       ws) -> Tuple[bool, Union[str, bytes]]:
        """_summary_

        Args:
            ws (connection): The ws connection.

        Raises:
            UnknownMessageReceived: The message is unexpected.

        Returns:
            Tuple[bool, str]: is output is binary, output
        """
        while True:
            msg = await ws.receive()
            await self._check_websocket_unexpected_message(msg)
            if msg.type == aiohttp.WSMsgType.TEXT:
                msg_json = msg.json()
                logger.debug('Receive %s event' % msg_json[HEADER][EVENT_KEY])
                if msg_json[HEADER][EVENT_KEY] == EventType.GENERATED:
                    payload = msg_json['payload']
                    return False, payload
                elif msg_json[HEADER][EVENT_KEY] == EventType.FINISHED:
                    payload = msg_json['payload']
                    return False, payload
                elif msg_json[HEADER][EVENT_KEY] == EventType.FAILED:
                    self._on_failed(msg_json)
                else:
                    error = 'Receive unknown message: %s' % msg_json
                    logger.error(error)
                    raise UnknownMessageReceived(error)
            elif msg.type == aiohttp.WSMsgType.BINARY:
                return True, msg.data  # get binary result data.

    async def _wait_for_task_started(self, ws):
        while True:
            msg = await ws.receive()
            await self._check_websocket_unexpected_message(msg)
            if msg.type == aiohttp.WSMsgType.TEXT:
                msg_json = msg.json()
                logger.debug('Receive %s event' % msg_json[HEADER][EVENT_KEY])
                if msg_json[HEADER][EVENT_KEY] == EventType.STARTED:
                    return
                elif msg_json[HEADER][EVENT_KEY] == EventType.FAILED:
                    self._on_failed(msg_json)
                else:
                    raise UnexpectedMessageReceived(
                        'Receive unexpected message, expect task-started, real: %s.'  # noqa E501
                        % msg_json[HEADER][EVENT_KEY])
            elif msg.type == aiohttp.WSMsgType.BINARY:
                raise UnexpectedMessageReceived(
                    'Receive unexpected binary message when wait for task-started'  # noqa E501
                )

    async def _check_websocket_unexpected_message(self, msg):
        if msg.type == aiohttp.WSMsgType.CLOSED:
            details = 'WSMsgType.CLOSE, data: %s, extra: %s' % (msg.data,
                                                                msg.extra)
            logger.error('Connection unexpected closed!')
            raise UnexpectedMessageReceived(
                'Receive unexpected websocket close message, details: %s' %
                details)
        elif msg.type == aiohttp.WSMsgType.ERROR:
            details = 'WSMsgType.ERROR, data: %s, extra: %s' % (msg.data,
                                                                msg.extra)
            logger.error('Connection error: %s' % details)
            raise UnexpectedMessageReceived(
                'Receive unexpected websocket error message details: %s.' %
                details)

    def _build_up_message(self, headers, payload):
        message = {'header': headers, 'payload': payload}
        return json.dumps(message)
