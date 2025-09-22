# Copyright (c) Alibaba, Inc. and its affiliates.

import time
from http import HTTPStatus
from typing import Any, Dict, Iterator, List, Union

import requests

import dashscope
from dashscope.api_entities.api_request_factory import _build_api_request
from dashscope.api_entities.dashscope_response import DashScopeAPIResponse
from dashscope.common.api_key import get_default_api_key
from dashscope.common.constants import (DEFAULT_REQUEST_TIMEOUT_SECONDS,
                                        REPEATABLE_STATUS,
                                        REQUEST_TIMEOUT_KEYWORD,
                                        SSE_CONTENT_TYPE, TaskStatus)
from dashscope.common.error import InvalidParameter, InvalidTask, ModelRequired
from dashscope.common.logging import logger
from dashscope.common.utils import (_handle_http_failed_response,
                                    _handle_http_response,
                                    _handle_http_stream_response,
                                    default_headers, join_url)


class BaseAioApi():
    """BaseApi, internal use only.

    """
    @classmethod
    def _validate_params(cls, api_key, model):
        if api_key is None:
            api_key = get_default_api_key()
        if model is None or not model:
            raise ModelRequired('Model is required!')
        return api_key, model

    @classmethod
    async def call(cls,
                   model: str,
                   input: object,
                   task_group: str,
                   task: str = None,
                   function: str = None,
                   api_key: str = None,
                   workspace: str = None,
                   **kwargs) -> DashScopeAPIResponse:
        """Call service and get result.

        Args:
            model (str): The requested model, such as gpt3-v2
            input (object): The api input data, cannot be None.
            task_group (str, optional): The api task group.
            task (str, optional): The task name. Defaults to None.
            function (str, optional): The function of the task.
                Defaults to None.
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.
            api_protocol (str, optional): Api protocol websocket or http.
                Defaults to None.
            ws_stream_mode (str, optional): websocket stream mode,
                [none, in, out, duplex]. Defaults to out.
            is_binary_input (bool, optional): Is input data binary.
                Defaults to False.
            http_method (str, optional): If api protocol is http, specifies
                method[GET, POST]. Defaults to POST.

        Returns:
            DashScopeAPIResponse: The service response.
        """
        api_key, model = BaseAioApi._validate_params(api_key, model)
        if workspace is not None:
            headers = {
                'X-DashScope-WorkSpace': workspace,
                **kwargs.pop('headers', {})
            }
            kwargs['headers'] = headers
        request = _build_api_request(model=model,
                                     input=input,
                                     task_group=task_group,
                                     task=task,
                                     function=function,
                                     api_key=api_key,
                                     **kwargs)
        # call request service.
        return await request.aio_call()


class BaseApi():
    """BaseApi, internal use only.

    """
    @classmethod
    def _validate_params(cls, api_key, model):
        if api_key is None:
            api_key = get_default_api_key()
        if model is None or not model:
            raise ModelRequired('Model is required!')
        return api_key, model

    @classmethod
    def call(cls,
             model: str,
             input: object,
             task_group: str,
             task: str = None,
             function: str = None,
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> DashScopeAPIResponse:
        """Call service and get result.

        Args:
            model (str): The requested model, such as gpt3-v2
            input (object): The api input data, cannot be None.
            task_group (str, optional): The api task group.
            task (str, optional): The task name. Defaults to None.
            function (str, optional): The function of the task.
                Defaults to None.
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.
            api_protocol (str, optional): Api protocol websocket or http.
                Defaults to None.
            ws_stream_mode (str, optional): websocket stream mode,
                [none, in, out, duplex]. Defaults to out.
            is_binary_input (bool, optional): Is input data binary.
                Defaults to False.
            http_method (str, optional): If api protocol is http, specifies
                method[GET, POST]. Defaults to POST.

        Returns:
            DashScopeAPIResponse: The service response.
        """
        api_key, model = BaseApi._validate_params(api_key, model)
        if workspace is not None:
            headers = {
                'X-DashScope-WorkSpace': workspace,
                **kwargs.pop('headers', {})
            }
            kwargs['headers'] = headers
        request = _build_api_request(model=model,
                                     input=input,
                                     task_group=task_group,
                                     task=task,
                                     function=function,
                                     api_key=api_key,
                                     **kwargs)
        # call request service.
        return request.call()


def _workspace_header(workspace) -> Dict:
    if workspace is not None:
        headers = {'X-DashScope-WorkSpace': workspace}
    else:
        headers = {}
    return headers


def _normalization_url(base_address, *args):
    if base_address:
        url = base_address
    else:
        url = dashscope.base_http_api_url
    return join_url(url, *args)


class AsyncTaskGetMixin():
    @classmethod
    def _get(cls,
             task_id: str,
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> DashScopeAPIResponse:
        base_url = kwargs.pop('base_address', None)
        status_url = _normalization_url(base_url, 'tasks', task_id)
        custom_headers = kwargs.pop('headers', None)
        headers = {
            **_workspace_header(workspace),
            **default_headers(api_key),
        }
        if custom_headers:
            headers = {
                **custom_headers,
                **headers,
            }
        with requests.Session() as session:
            logger.debug('Starting request: %s' % status_url)
            response = session.get(status_url,
                                   headers=headers,
                                   timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS)
            logger.debug('Starting processing response: %s' % status_url)
            return _handle_http_response(response)


class BaseAsyncApi(AsyncTaskGetMixin):
    """BaseAsyncApi,for async task, internal use only.

    """
    @classmethod
    def _validate_params(cls, api_key, model):
        if api_key is None:
            api_key = get_default_api_key()
        if model is None or not model:
            raise ModelRequired('Model is required!')
        return api_key, model

    @classmethod
    def call(cls,
             *args,
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> DashScopeAPIResponse:
        """Call service and get result.
        """
        task_response = cls.async_call(*args,
                                       api_key=api_key,
                                       workspace=workspace,
                                       **kwargs)
        response = cls.wait(task_response,
                            api_key=api_key,
                            workspace=workspace)
        return response

    @classmethod
    def _get_task_id(cls, task):
        if isinstance(task, str):
            task_id = task
        elif isinstance(task, DashScopeAPIResponse):
            if task.status_code == HTTPStatus.OK:
                task_id = task.output['task_id']
            else:
                raise InvalidTask('Invalid task, task create failed: %s' %
                                  task)
        else:
            raise InvalidParameter('Task invalid!')
        if task_id is None or task_id == '':
            raise InvalidParameter('Task id required!')
        return task_id

    @classmethod
    def cancel(
        cls,
        task: Union[str, DashScopeAPIResponse],
        api_key: str = None,
        workspace: str = None,
        **kwargs,
    ) -> DashScopeAPIResponse:
        """Cancel PENDING task.

        Args:
            task (Union[str, DashScopeAPIResponse]): The task_id, or
                async_call response.
            api_key (str, optional): The api-key. Defaults to None.

        Returns:
            DashScopeAPIResponse: The cancel result.
        """
        task_id = cls._get_task_id(task)
        base_url = kwargs.pop('base_address', None)
        url = _normalization_url(base_url, 'tasks', task_id, 'cancel')
        with requests.Session() as session:
            response = session.post(url,
                                    headers={
                                        **_workspace_header(workspace),
                                        **default_headers(api_key),
                                    })
            return _handle_http_response(response)

    @classmethod
    def list(cls,
             start_time: str = None,
             end_time: str = None,
             model_name: str = None,
             api_key_id: str = None,
             region: str = None,
             status: str = None,
             page_no: int = 1,
             page_size: int = 10,
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> DashScopeAPIResponse:
        """List async tasks.

        Args:
            start_time (str, optional): The tasks start time,
                for example: 20230420000000. Defaults to None.
            end_time (str, optional): The tasks end time,
                for example: 20230420000000. Defaults to None.
            model_name (str, optional): The tasks model name.
                Defaults to None.
            api_key_id (str, optional): The tasks api-key-id.
                Defaults to None.
            region (str, optional): The service region,
                for example: cn-beijing. Defaults to None.
            status (str, optional): The status of tasks[PENDING,
                RUNNING, SUCCEEDED, FAILED, CANCELED]. Defaults to None.
            page_no (int, optional): The page number. Defaults to 1.
            page_size (int, optional): The page size. Defaults to 10.
            api_key (str, optional): The user api-key. Defaults to None.

        Returns:
            DashScopeAPIResponse: The response data.
        """
        base_url = kwargs.pop('base_address', None)
        url = _normalization_url(base_url, 'tasks')
        params = {'page_no': page_no, 'page_size': page_size}
        if start_time is not None:
            params['start_time'] = start_time
        if end_time is not None:
            params['end_time'] = end_time
        if model_name is not None:
            params['model_name'] = model_name
        if api_key_id is not None:
            params['api_key_id'] = api_key_id
        if region is not None:
            params['region'] = region
        if status is not None:
            params['status'] = status

        with requests.Session() as session:
            response = session.get(url,
                                   params=params,
                                   headers={
                                       **_workspace_header(workspace),
                                       **default_headers(api_key),
                                   })
            if response.status_code == HTTPStatus.OK:
                json_content = response.json()
                request_id = ''
                if 'request_id' in json_content:
                    request_id = json_content['request_id']
                    json_content.pop('request_id')
                return DashScopeAPIResponse(request_id=request_id,
                                            status_code=response.status_code,
                                            code=None,
                                            output=json_content,
                                            usage=None,
                                            message='')
            else:
                return _handle_http_failed_response(response)

    @classmethod
    def fetch(
        cls,
        task: Union[str, DashScopeAPIResponse],
        api_key: str = None,
        workspace: str = None,
        **kwargs,
    ) -> DashScopeAPIResponse:
        """Query async task status.

        Args:
            task (Union[str, DashScopeAPIResponse]): The task_id, or
                async_call response.
            api_key (str, optional): The api_key. Defaults to None.

        Returns:
            DashScopeAPIResponse: The async task information.
        """
        task_id = cls._get_task_id(task)
        return cls._get(task_id, api_key, workspace, **kwargs)

    @classmethod
    def wait(cls,
             task: Union[str, DashScopeAPIResponse],
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> DashScopeAPIResponse:
        """Wait for async task completion and return task result.

        Args:
            task (Union[str, DashScopeAPIResponse]): The task_id, or
                async_call response.
            api_key (str, optional): The api_key. Defaults to None.

        Returns:
            DashScopeAPIResponse: The async task information.
        """
        task_id = cls._get_task_id(task)
        wait_seconds = 1
        max_wait_seconds = 5
        increment_steps = 3
        step = 0
        while True:
            step += 1
            # we start by querying once every second, and double
            # the query interval after every 3(increment_steps)
            # intervals, until we hit the max waiting interval
            # of 5(seconds）
            # TODO: investigate if we can use long-poll
            # (server side return immediately when ready)
            if wait_seconds < max_wait_seconds and step % increment_steps == 0:
                wait_seconds = min(wait_seconds * 2, max_wait_seconds)
            rsp = cls._get(task_id, api_key, workspace=workspace, **kwargs)
            if rsp.status_code == HTTPStatus.OK:
                if rsp.output is None:
                    return rsp

                task_status = rsp.output['task_status']
                if task_status in [
                        TaskStatus.FAILED, TaskStatus.CANCELED,
                        TaskStatus.SUCCEEDED, TaskStatus.UNKNOWN
                ]:
                    return rsp
                else:
                    logger.info('The task %s is  %s' % (task_id, task_status))
                    time.sleep(wait_seconds)
            elif rsp.status_code in REPEATABLE_STATUS:
                logger.warn(
                    ('Get task: %s temporary failure, \
                        status_code: %s, code: %s message: %s, will try again.'
                     ) % (task_id, rsp.status_code, rsp.code, rsp.message))
                time.sleep(wait_seconds)
            else:
                return rsp

    @classmethod
    def async_call(cls,
                   model: str,
                   input: object,
                   task_group: str,
                   task: str = None,
                   function: str = None,
                   api_key: str = None,
                   workspace: str = None,
                   **kwargs) -> DashScopeAPIResponse:
        """Call async service return async task information.

        Args:
            model (str): The requested model, such as gpt3-v2
            input (object): The api input data, cannot be None.
            task_group (str, optional): The api task group.
            task (str, optional): The task name. Defaults to None.
            function (str, optional): The function of the task.
                Defaults to None.
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.

        Returns:
            DashScopeAPIResponse: The async task information,
                which contains the task id, you can use the task id
                to query the task status.
        """
        is_stream = kwargs.pop('stream', None)  # async api not support stream.
        if is_stream:
            logger.warn('async_call do not support stream argument')
        api_key, model = BaseApi._validate_params(api_key, model)
        if workspace is not None:
            headers = {
                'X-DashScope-WorkSpace': workspace,
                **kwargs.pop('headers', {})
            }
            kwargs['headers'] = headers
        request = _build_api_request(model=model,
                                     input=input,
                                     task_group=task_group,
                                     task=task,
                                     function=function,
                                     api_key=api_key,
                                     async_request=True,
                                     query=False,
                                     **kwargs)
        return request.call()


def _get(url,
         params={},
         api_key=None,
         flattened_output=False,
         workspace: str = None,
         **kwargs) -> Union[DashScopeAPIResponse, Dict]:
    timeout = kwargs.pop(REQUEST_TIMEOUT_KEYWORD,
                         DEFAULT_REQUEST_TIMEOUT_SECONDS)
    with requests.Session() as session:
        logger.debug('Starting request: %s' % url)
        response = session.get(url,
                               headers={
                                   **_workspace_header(workspace),
                                   **default_headers(api_key),
                                   **kwargs.pop('headers', {})
                               },
                               params=params,
                               timeout=timeout)
        logger.debug('Starting processing response: %s' % url)
        return _handle_http_response(response, flattened_output)


def _get_url(custom_base_url, default_path, path):
    if not custom_base_url:
        base_url = dashscope.base_http_api_url
    else:
        base_url = custom_base_url
    if path is not None:
        url = join_url(base_url, path)
    else:
        url = join_url(base_url, default_path)
    return url


class ListObjectMixin():
    @classmethod
    def list(cls,
             limit: int = None,
             order: str = None,
             after: str = None,
             before: str = None,
             path: str = None,
             workspace: str = None,
             api_key: str = None,
             **kwargs) -> Any:
        """List object

        Args:
            limit (int, optional): How many object to list. Defaults to None.
            order (str, optional): The order of result. Defaults to None.
            after (str, optional): The id of the object begin. Defaults to None.
            before (str, optional): The if of the object end. Defaults to None.
            path (str, optional): The request path. Defaults to None.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): The DashScope api_key. Defaults to None.

        Returns:
            Any: The object list.
        """
        custom_base_url = kwargs.pop('base_address', None)
        url = _get_url(custom_base_url, cls.SUB_PATH.lower(), path)
        params = {}
        if limit is not None:
            if limit < 0:
                raise InvalidParameter('limit should >= 0')
            params['limit'] = limit
        if order is not None:
            params['order'] = order
        if after is not None:
            params['after'] = after
        if before is not None:
            params['before'] = before
        return _get(url,
                    params=params,
                    api_key=api_key,
                    workspace=workspace,
                    **kwargs)


class ListMixin():
    @classmethod
    def list(cls,
             page_no=1,
             page_size=10,
             api_key: str = None,
             path: str = None,
             workspace: str = None,
             **kwargs) -> Union[DashScopeAPIResponse, Dict]:
        """list objects

        Args:
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.
            path (str, optional): The path of the api, if not default.
            page_no (int, optional): Page number. Defaults to 1.
            page_size (int, optional): Items per page. Defaults to 10.

        Returns:
            DashScopeAPIResponse: The object list in output.
        """
        custom_base_url = kwargs.pop('base_address', None)
        url = _get_url(custom_base_url, cls.SUB_PATH.lower(), path)
        params = {'page_no': page_no, 'page_size': page_size}
        return _get(url,
                    params=params,
                    api_key=api_key,
                    workspace=workspace,
                    **kwargs)


class LogMixin():
    @classmethod
    def logs(cls,
             job_id: str,
             offset=1,
             line=1000,
             api_key: str = None,
             path: str = None,
             workspace: str = None,
             **kwargs) -> Union[DashScopeAPIResponse, Dict]:
        """Get log of the job.

        Args:
            job_id (str): The job id(used for fine-tune)
            offset (int, optional): start log line. Defaults to 1.
            line (int, optional): total line return. Defaults to 1000.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            DashScopeAPIResponse: The response
        """
        custom_base_url = kwargs.pop('base_address', None)
        if not custom_base_url:
            url = join_url(dashscope.base_http_api_url, cls.SUB_PATH.lower(),
                           job_id, 'logs')
        else:
            url = custom_base_url
        params = {'offset': offset, 'line': line}
        return _get(url,
                    params=params,
                    api_key=api_key,
                    workspace=workspace,
                    **kwargs)


class GetMixin():
    @classmethod
    def get(cls,
            target,
            api_key: str = None,
            params: dict = {},
            path: str = None,
            workspace: str = None,
            **kwargs) -> Union[DashScopeAPIResponse, Dict]:
        """Get object information.

        Args:
            target (str): The target to get, such as model_id.
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.

        Returns:
            DashScopeAPIResponse: The object information in output.
        """
        custom_base_url = kwargs.pop('base_address', None)
        if custom_base_url:
            base_url = custom_base_url
        else:
            base_url = dashscope.base_http_api_url

        if path is not None:
            url = join_url(base_url, path)
        else:
            url = join_url(base_url, cls.SUB_PATH.lower(), target)
        flattened_output = kwargs.pop('flattened_output', False)
        return _get(url,
                    api_key=api_key,
                    params=params,
                    flattened_output=flattened_output,
                    workspace=workspace,
                    **kwargs)


class GetStatusMixin():
    @classmethod
    def get(cls,
            target,
            api_key: str = None,
            path: str = None,
            workspace: str = None,
            **kwargs) -> Union[DashScopeAPIResponse, Dict]:
        """Get object information.

        Args:
            target (str): The target to get, such as model_id.
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.

        Returns:
            DashScopeAPIResponse: The object information in output.
        """
        custom_base_url = kwargs.pop('base_address', None)
        if custom_base_url:
            base_url = custom_base_url
        else:
            base_url = dashscope.base_http_api_url
        if path is not None:
            url = join_url(base_url, path)
        else:
            url = join_url(base_url, cls.SUB_PATH.lower(), target)
        flattened_output = kwargs.pop('flattened_output', False)
        return _get(url,
                    api_key=api_key,
                    flattened_output=flattened_output,
                    workspace=workspace,
                    **kwargs)


class DeleteMixin():
    @classmethod
    def delete(cls,
               target: str,
               api_key: str = None,
               path: str = None,
               workspace: str = None,
               flattened_output=False,
               **kwargs) -> Union[DashScopeAPIResponse, Dict]:
        """Delete object.

        Args:
            target (str): The object to delete, .
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.

        Returns:
            DashScopeAPIResponse: The delete result.
        """
        custom_base_url = kwargs.pop('base_address', None)
        if custom_base_url:
            base_url = custom_base_url
        else:
            base_url = dashscope.base_http_api_url
        if path is not None:
            url = join_url(base_url, path)
        else:
            url = join_url(base_url, cls.SUB_PATH.lower(), target)
        timeout = kwargs.pop(REQUEST_TIMEOUT_KEYWORD,
                             DEFAULT_REQUEST_TIMEOUT_SECONDS)
        with requests.Session() as session:
            logger.debug('Starting request: %s' % url)
            response = session.delete(url,
                                      headers={
                                          **_workspace_header(workspace),
                                          **default_headers(api_key),
                                          **kwargs.pop('headers', {})
                                      },
                                      timeout=timeout)
            logger.debug('Starting processing response: %s' % url)
            return _handle_http_response(response, flattened_output)


class CreateMixin():
    @classmethod
    def call(cls,
             data: object,
             api_key: str = None,
             path: str = None,
             stream: bool = False,
             workspace: str = None,
             **kwargs) -> Union[DashScopeAPIResponse, Dict]:
        """Create a object

        Args:
            data (object): The create request json body.
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.

        Returns:
            DashScopeAPIResponse: The created object in output.
        """
        url = _get_url(kwargs.pop('base_address', None), cls.SUB_PATH.lower(),
                       path)
        timeout = kwargs.pop(REQUEST_TIMEOUT_KEYWORD,
                             DEFAULT_REQUEST_TIMEOUT_SECONDS)
        flattened_output = kwargs.pop('flattened_output', False)
        with requests.Session() as session:
            logger.debug('Starting request: %s' % url)
            response = session.post(url,
                                    json=data,
                                    stream=stream,
                                    headers={
                                        **_workspace_header(workspace),
                                        **default_headers(api_key),
                                        **kwargs.pop('headers', {})
                                    },
                                    timeout=timeout)
            logger.debug('Starting processing response: %s' % url)
            response = _handle_http_stream_response(response, flattened_output)
            if stream:
                return (item for item in response)
            else:
                _, output = next(response)
                try:
                    next(response)
                except StopIteration:
                    pass
                return output


class UpdateMixin():
    @classmethod
    def update(cls,
               target: str,
               json: object,
               api_key: str = None,
               path: str = None,
               workspace: str = None,
               method: str = 'patch',
               **kwargs) -> Union[DashScopeAPIResponse, Dict]:
        """Async update a object

        Args:
            target (str): The target to update.
            json (object): The create request json body.
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.

        Returns:
            DashScopeAPIResponse: The updated object information in output.
        """
        custom_base_url = kwargs.pop('base_address', None)
        if custom_base_url:
            base_url = custom_base_url
        else:
            base_url = dashscope.base_http_api_url
        if path is not None:
            url = join_url(base_url, path)
        else:
            url = join_url(base_url, cls.SUB_PATH.lower(), target)
        timeout = kwargs.pop(REQUEST_TIMEOUT_KEYWORD,
                             DEFAULT_REQUEST_TIMEOUT_SECONDS)
        flattened_output = kwargs.pop('flattened_output', False)
        with requests.Session() as session:
            logger.debug('Starting request: %s' % url)
            if method == 'post':
                response = session.post(url,
                                        json=json,
                                        headers={
                                            **_workspace_header(workspace),
                                            **default_headers(api_key),
                                            **kwargs.pop('headers', {})
                                        },
                                        timeout=timeout)
            else:
                response = session.patch(url,
                                         json=json,
                                         headers={
                                             **_workspace_header(workspace),
                                             **default_headers(api_key),
                                             **kwargs.pop('headers', {})
                                         },
                                         timeout=timeout)
            logger.debug('Starting processing response: %s' % url)
            return _handle_http_response(response, flattened_output)


class PutMixin():
    @classmethod
    def put(cls,
            target: str,
            json: object,
            path: str = None,
            api_key: str = None,
            workspace: str = None,
            **kwargs) -> Union[DashScopeAPIResponse, Dict]:
        """Async update a object

        Args:
            target (str): The target to update.
            json (object): The create request json body.
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.

        Returns:
            DashScopeAPIResponse: The updated object information in output.
        """
        custom_base_url = kwargs.pop('base_address', None)
        if custom_base_url:
            base_url = custom_base_url
        else:
            base_url = dashscope.base_http_api_url
        if path is None:
            url = join_url(base_url, cls.SUB_PATH.lower(), target)
        else:
            url = join_url(base_url, path)
        timeout = kwargs.pop(REQUEST_TIMEOUT_KEYWORD,
                             DEFAULT_REQUEST_TIMEOUT_SECONDS)
        with requests.Session() as session:
            logger.debug('Starting request: %s' % url)
            response = session.put(url,
                                   json=json,
                                   headers={
                                       **_workspace_header(workspace),
                                       **default_headers(api_key),
                                       **kwargs.pop('headers', {})
                                   },
                                   timeout=timeout)
            logger.debug('Starting processing response: %s' % url)
            return _handle_http_response(response)


class FileUploadMixin():
    @classmethod
    def upload(cls,
               files: list,
               descriptions: List[str] = None,
               params: dict = None,
               api_key: str = None,
               workspace: str = None,
               **kwargs) -> Union[DashScopeAPIResponse, Dict]:
        """Upload files

        Args:
            files (list): List of (name, opened file, file_name).
            descriptions (list[str]): The file description messages.
            params (dict): The parameters
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.

        Returns:
            DashScopeAPIResponse: The uploaded file information in the output.
        """
        custom_base_url = kwargs.pop('base_address', None)
        if custom_base_url:
            base_url = custom_base_url
        else:
            base_url = dashscope.base_http_api_url
        url = join_url(base_url, cls.SUB_PATH.lower())
        js = None
        if descriptions:
            js = {'descriptions': descriptions}
        timeout = kwargs.pop(REQUEST_TIMEOUT_KEYWORD,
                             DEFAULT_REQUEST_TIMEOUT_SECONDS)
        with requests.Session() as session:
            logger.debug('Starting request: %s' % url)
            response = session.post(url,
                                    data=js,
                                    headers={
                                        **_workspace_header(workspace),
                                        **default_headers(api_key),
                                        **kwargs.pop('headers', {})
                                    },
                                    files=files,
                                    timeout=timeout)
            logger.debug('Starting processing response: %s' % url)
            return _handle_http_response(response)


class CancelMixin():
    @classmethod
    def cancel(cls,
               target: str,
               path: str = None,
               api_key: str = None,
               workspace: str = None,
               **kwargs) -> Union[DashScopeAPIResponse, Dict]:
        """Cancel a job.

        Args:
            target (str): The request params, key/value map.
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.

        Returns:
            DashScopeAPIResponse: The cancel result.
        """
        custom_base_url = kwargs.pop('base_address', None)
        if custom_base_url:
            base_url = custom_base_url
        else:
            base_url = dashscope.base_http_api_url
        if not path:
            url = join_url(base_url, cls.SUB_PATH.lower(), target, 'cancel')
        else:
            url = join_url(base_url, path)
        timeout = kwargs.pop(REQUEST_TIMEOUT_KEYWORD,
                             DEFAULT_REQUEST_TIMEOUT_SECONDS)
        flattened_output = kwargs.pop('flattened_output', False)
        with requests.Session() as session:
            logger.debug('Starting request: %s' % url)
            response = session.post(url,
                                    headers={
                                        **_workspace_header(workspace),
                                        **default_headers(api_key),
                                        **kwargs.pop('headers', {})
                                    },
                                    timeout=timeout)
            logger.debug('Starting processing response: %s' % url)
            return _handle_http_response(response, flattened_output)


class StreamEventMixin():
    @classmethod
    def _handle_stream(cls, response: requests.Response):
        # TODO define done message.
        is_error = False
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        for line in response.iter_lines():
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

    @classmethod
    def _handle_response(cls, response: requests.Response):
        request_id = ''
        if (response.status_code == HTTPStatus.OK
                and SSE_CONTENT_TYPE in response.headers.get(
                    'content-type', '')):
            for is_error, status_code, data in cls._handle_stream(response):
                if is_error:
                    yield DashScopeAPIResponse(request_id=request_id,
                                               status_code=status_code,
                                               output=None,
                                               code='',
                                               message='')  # noqa E501
                else:
                    yield DashScopeAPIResponse(request_id=request_id,
                                               status_code=HTTPStatus.OK,
                                               output=data,
                                               usage=None)
        elif response.status_code == HTTPStatus.OK:
            json_content = response.json()
            request_id = ''
            if 'request_id' in json_content:
                request_id = json_content['request_id']
            yield DashScopeAPIResponse(request_id=request_id,
                                       status_code=HTTPStatus.OK,
                                       output=json_content,
                                       usage=None)
        else:
            yield _handle_http_failed_response(response)

    @classmethod
    def stream_events(cls,
                      target,
                      api_key: str = None,
                      workspace: str = None,
                      **kwargs) -> Iterator[DashScopeAPIResponse]:
        """Get job log.

        Args:
            target (str): The target to get, such as model_id.
            api_key (str, optional): The api api_key, if not present,
                will get by default rule(TODO: api key doc). Defaults to None.

        Returns:
            DashScopeAPIResponse: The target outputs.
        """
        custom_base_url = kwargs.pop('base_address', None)
        if custom_base_url:
            base_url = custom_base_url
        else:
            base_url = dashscope.base_http_api_url
        url = join_url(base_url, cls.SUB_PATH.lower(), target, 'stream')
        timeout = kwargs.pop(REQUEST_TIMEOUT_KEYWORD,
                             DEFAULT_REQUEST_TIMEOUT_SECONDS)
        with requests.Session() as session:
            logger.debug('Starting request: %s' % url)
            response = session.get(url,
                                   headers={
                                       **_workspace_header(workspace),
                                       **default_headers(api_key),
                                       **kwargs.pop('headers', {})
                                   },
                                   stream=True,
                                   timeout=timeout)
            logger.debug('Starting processing response: %s' % url)
            for rsp in cls._handle_response(response):
                yield rsp
