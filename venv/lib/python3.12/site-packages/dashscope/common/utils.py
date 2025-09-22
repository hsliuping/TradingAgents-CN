# Copyright (c) Alibaba, Inc. and its affiliates.

import asyncio
import json
import os
import platform
import queue
import threading
from dataclasses import dataclass
from http import HTTPStatus
from typing import Dict
from urllib.parse import urlparse

import aiohttp
import requests

from dashscope.api_entities.dashscope_response import DashScopeAPIResponse
from dashscope.common.api_key import get_default_api_key
from dashscope.common.constants import SSE_CONTENT_TYPE
from dashscope.common.logging import logger
from dashscope.version import __version__


def is_validate_fine_tune_file(file_path):
    with open(file_path, encoding='utf-8') as f:
        for line in f:
            try:
                json.loads(line)
            except json.decoder.JSONDecodeError:
                return False
    return True


def _get_task_group_and_task(module_name):
    """Get task_group and task name.
    get task_group and task name based on api file __name__

    Args:
        module_name (str): The api file __name__

    Returns:
        (str, str): task_group and task
    """
    pkg, task = module_name.rsplit('.', 1)
    task = task.replace('_', '-')
    _, task_group = pkg.rsplit('.', 1)
    return task_group, task


def is_path(path: str):
    """Check the input path is valid local path.

    Args:
        path_or_url (str): The path.

    Returns:
        bool: If path return True, otherwise False.
    """
    url_parsed = urlparse(path)
    if url_parsed.scheme in ('file', ''):
        return os.path.exists(url_parsed.path)
    else:
        return False


def is_url(url: str):
    """Check the input url is valid url.

    Args:
        url (str): The url

    Returns:
        bool: If is url return True, otherwise False.
    """
    url_parsed = urlparse(url)
    if url_parsed.scheme in ('http', 'https', 'oss'):
        return True
    else:
        return False


def iter_over_async(ait):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    ait = ait.__aiter__()

    async def get_next():
        try:
            obj = await ait.__anext__()
            return False, obj
        except StopAsyncIteration:
            return True, None

    def iter_thread(loop, message_queue):
        while True:
            try:
                done, obj = loop.run_until_complete(get_next())
                if done:
                    message_queue.put((True, None, None))
                    break
                message_queue.put((False, None, obj))
            except BaseException as e:  # noqa E722
                logger.exception(e)
                message_queue.put((True, e, None))
                break

    message_queue = queue.Queue()
    x = threading.Thread(target=iter_thread,
                         args=(loop, message_queue),
                         name='iter_async_thread')
    x.start()
    while True:
        finished, error, obj = message_queue.get()
        if finished:
            if error is not None:
                yield DashScopeAPIResponse(
                    -1,
                    '',
                    'Unknown',
                    message='Error type: %s, message: %s' %
                    (type(error), error))
            break
        else:
            yield obj


def async_to_sync(async_generator):
    for message in iter_over_async(async_generator):
        yield message


def get_user_agent():
    ua = 'dashscope/%s; python/%s; platform/%s; processor/%s' % (
        __version__,
        platform.python_version(),
        platform.platform(),
        platform.processor(),
    )
    return ua


def default_headers(api_key: str = None) -> Dict[str, str]:
    ua = 'dashscope/%s; python/%s; platform/%s; processor/%s' % (
        __version__,
        platform.python_version(),
        platform.platform(),
        platform.processor(),
    )
    headers = {'user-agent': ua}
    if api_key is None:
        api_key = get_default_api_key()
    headers['Authorization'] = 'Bearer %s' % api_key
    headers['Accept'] = 'application/json'
    return headers


def join_url(base_url, *args):
    if not base_url.endswith('/'):
        base_url = base_url + '/'
    url = base_url
    for arg in args:
        if arg is not None:
            url += arg + '/'
    return url[:-1]


async def _handle_aiohttp_response(response: aiohttp.ClientResponse):
    request_id = ''
    if response.status == HTTPStatus.OK:
        json_content = await response.json()
        if 'request_id' in json_content:
            request_id = json_content['request_id']
        return DashScopeAPIResponse(request_id=request_id,
                                    status_code=HTTPStatus.OK,
                                    output=json_content)
    else:
        if 'application/json' in response.content_type:
            error = await response.json()
            msg = ''
            if 'message' in error:
                msg = error['message']
            if 'request_id' in error:
                request_id = error['request_id']
            return DashScopeAPIResponse(request_id=request_id,
                                        status_code=response.status,
                                        output=None,
                                        code=error['code'],
                                        message=msg)
        else:
            msg = await response.read()
            return DashScopeAPIResponse(request_id=request_id,
                                        status_code=response.status,
                                        output=None,
                                        code='Unknown',
                                        message=msg)


@dataclass
class SSEEvent:
    id: str
    eventType: str
    data: str

    def __init__(self, id: str, type: str, data: str):
        self.id = id
        self.eventType = type
        self.data = data


def _handle_stream(response: requests.Response):
    # TODO define done message.
    is_error = False
    status_code = HTTPStatus.BAD_REQUEST
    event = SSEEvent(None, None, None)
    eventType = None
    for line in response.iter_lines():
        if line:
            line = line.decode('utf8')
            line = line.rstrip('\n').rstrip('\r')
            if line.startswith('id:'):
                id = line[len('id:'):]
                event.id = id.strip()
            elif line.startswith('event:'):
                eventType = line[len('event:'):]
                event.eventType = eventType.strip()
                if eventType == 'error':
                    is_error = True
            elif line.startswith('status:'):
                status_code = line[len('status:'):]
                status_code = int(status_code.strip())
            elif line.startswith('data:'):
                line = line[len('data:'):]
                event.data = line.strip()
                if eventType is not None and eventType == 'done':
                    continue
                yield (is_error, status_code, event)
                if is_error:
                    break
            else:
                continue  # ignore heartbeat...


def _handle_error_message(error, status_code, flattened_output):
    code = None
    msg = ''
    request_id = ''
    if flattened_output:
        error['status_code'] = status_code
        return error
    if 'message' in error:
        msg = error['message']
    if 'msg' in error:
        msg = error['msg']
    if 'code' in error:
        code = error['code']
    if 'request_id' in error:
        request_id = error['request_id']
    return DashScopeAPIResponse(request_id=request_id,
                                status_code=status_code,
                                code=code,
                                message=msg)


def _handle_http_failed_response(
        response: requests.Response,
        flattened_output: bool = False) -> DashScopeAPIResponse:
    request_id = ''
    if 'application/json' in response.headers.get('content-type', ''):
        error = response.json()
        return _handle_error_message(error, response.status_code,
                                     flattened_output)
    elif SSE_CONTENT_TYPE in response.headers.get('content-type', ''):
        msgs = response.content.decode('utf-8').split('\n')
        for msg in msgs:
            if msg.startswith('data:'):
                error = json.loads(msg.replace('data:', '').strip())
                return _handle_error_message(error, response.status_code,
                                             flattened_output)
        return DashScopeAPIResponse(request_id=request_id,
                                    status_code=response.status_code,
                                    code='Unknown',
                                    message=msgs)
    else:
        msg = response.content.decode('utf-8')
        if flattened_output:
            return {'status_code': response.status_code, 'message': msg}
        return DashScopeAPIResponse(request_id=request_id,
                                    status_code=response.status_code,
                                    code='Unknown',
                                    message=msg)


async def _handle_aio_stream(response):
    # TODO define done message.
    is_error = False
    status_code = HTTPStatus.BAD_REQUEST
    async for line in response.content:
        if line:
            line = line.decode('utf8')
            line = line.rstrip('\n').rstrip('\r')
            if line.startswith('event:error'):
                is_error = True
            elif line.startswith('status:'):
                status_code = line[len('status:'):]
                status_code = int(status_code.strip())
            elif line.startswith('data:'):
                line = line[len('data:'):]
                yield (is_error, status_code, line)
                if is_error:
                    break
            else:
                continue  # ignore heartbeat...


async def _handle_aiohttp_failed_response(
        response: requests.Response,
        flattened_output: bool = False) -> DashScopeAPIResponse:
    request_id = ''
    if 'application/json' in response.content_type:
        error = await response.json()
        return _handle_error_message(error, response.status, flattened_output)
    elif SSE_CONTENT_TYPE in response.content_type:
        async for _, _, data in _handle_aio_stream(response):
            error = json.loads(data)
        return _handle_error_message(error, response.status, flattened_output)
    else:
        msg = response.content.decode('utf-8')
        if flattened_output:
            return {'status_code': response.status, 'message': msg}
        return DashScopeAPIResponse(request_id=request_id,
                                    status_code=response.status,
                                    code='Unknown',
                                    message=msg)


def _handle_http_response(response: requests.Response,
                          flattened_output: bool = False):
    response = _handle_http_stream_response(response, flattened_output)
    _, output = next(response)
    try:
        next(response)
    except StopIteration:
        pass
    return output


def _handle_http_stream_response(response: requests.Response,
                                 flattened_output: bool = False):
    request_id = ''
    if (response.status_code == HTTPStatus.OK
            and SSE_CONTENT_TYPE in response.headers.get('content-type', '')):
        for is_error, status_code, event in _handle_stream(response):
            if not is_error:
                try:
                    output = None
                    usage = None
                    msg = json.loads(event.data)
                    if flattened_output:
                        msg['status_code'] = response.status_code
                        yield event.eventType, msg
                    else:
                        logger.debug('Stream message: %s' % msg)
                        if not is_error:
                            if 'output' in msg:
                                output = msg['output']
                            if 'usage' in msg:
                                usage = msg['usage']
                        if 'request_id' in msg:
                            request_id = msg['request_id']
                        yield event.eventType, DashScopeAPIResponse(
                            request_id=request_id,
                            status_code=HTTPStatus.OK,
                            output=output,
                            usage=usage)
                except json.JSONDecodeError as e:
                    if flattened_output:
                        yield event.eventType, {
                            'status_code': response.status_code,
                            'message': e.message
                        }
                    else:
                        yield event.eventType, DashScopeAPIResponse(
                            request_id=request_id,
                            status_code=HTTPStatus.BAD_REQUEST,
                            output=None,
                            code='Unknown',
                            message=event.data)
                    continue
            else:
                if flattened_output:
                    yield event.eventType, {
                        'status_code': status_code,
                        'message': event.data
                    }
                else:
                    msg = json.loads(event.eventType)
                    yield event.eventType, DashScopeAPIResponse(
                        request_id=request_id,
                        status_code=status_code,
                        output=None,
                        code=msg['code']
                        if 'code' in msg else None,  # noqa E501
                        message=msg['message']
                        if 'message' in msg else None)  # noqa E501
    elif response.status_code == HTTPStatus.OK or response.status_code == HTTPStatus.CREATED:
        json_content = response.json()
        if flattened_output:
            json_content['status_code'] = response.status_code
            yield None, json_content
        else:
            output = None
            usage = None
            code = None
            msg = ''
            if 'data' in json_content:
                output = json_content['data']
            if 'code' in json_content:
                code = json_content['code']
            if 'message' in json_content:
                msg = json_content['message']
            if 'output' in json_content:
                output = json_content['output']
            if 'usage' in json_content:
                usage = json_content['usage']
            if 'request_id' in json_content:
                request_id = json_content['request_id']
                json_content.pop('request_id', None)

            if 'data' not in json_content and 'output' not in json_content:
                output = json_content

            yield None, DashScopeAPIResponse(request_id=request_id,
                                             status_code=response.status_code,
                                             code=code,
                                             output=output,
                                             usage=usage,
                                             message=msg)
    else:
        yield None, _handle_http_failed_response(response, flattened_output)
