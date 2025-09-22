# Copyright (c) Alibaba, Inc. and its affiliates.

import time
from http import HTTPStatus
from typing import Dict, List, Optional

from dashscope.client.base_api import (CancelMixin, CreateMixin,
                                       GetStatusMixin, ListObjectMixin,
                                       UpdateMixin)
from dashscope.common.error import (AssistantError, InputRequired,
                                    TimeoutException)
from dashscope.common.logging import logger
from dashscope.threads.thread_types import (Run, RunList, RunStep,
                                            RunStepDelta, Thread,
                                            ThreadMessage, ThreadMessageDelta)

__all__ = ['Runs']


class Runs(CreateMixin, CancelMixin, ListObjectMixin, GetStatusMixin,
           UpdateMixin):
    SUB_PATH = 'RUNS'  # useless

    @classmethod
    def create_thread_and_run(cls,
                              *,
                              assistant_id: str,
                              thread: Optional[Dict] = None,
                              model: Optional[str] = None,
                              instructions: Optional[str] = None,
                              additional_instructions: Optional[str] = None,
                              tools: Optional[List[Dict]] = None,
                              stream: Optional[bool] = False,
                              metadata: Optional[Dict] = None,
                              workspace: str = None,
                              extra_body: Optional[Dict] = None,
                              api_key: str = None,
                              **kwargs) -> Run:
        if not assistant_id:
            raise InputRequired('assistant_id is required')
        data = {'assistant_id': assistant_id}
        if thread:
            data['thread'] = thread
        if model:
            data['model'] = model
        if instructions:
            data['instructions'] = instructions
        if additional_instructions:
            data['additional_instructions'] = additional_instructions
        if tools:
            data['tools'] = tools
        if metadata:
            data['metadata'] = metadata
        data['stream'] = stream
        if extra_body is not None and extra_body:
            data = {**data, **extra_body}

        response = super().call(data=data,
                                path='threads/runs',
                                api_key=api_key,
                                flattened_output=True,
                                stream=stream,
                                workspace=workspace,
                                **kwargs)
        if stream:
            return ((event_type, cls.convert_stream_object(event_type, item))
                    for event_type, item in response)
        else:
            return Run(**response)

    @classmethod
    def create(cls,
               thread_id: str,
               *,
               assistant_id: str,
               model: Optional[str] = None,
               instructions: Optional[str] = None,
               additional_instructions: Optional[str] = None,
               tools: Optional[List[Dict]] = None,
               metadata: Optional[Dict] = None,
               stream: Optional[bool] = False,
               workspace: str = None,
               extra_body: Optional[Dict] = None,
               api_key: str = None,
               top_p: Optional[float] = None,
               top_k: Optional[int] = None,
               temperature: Optional[float] = None,
               max_tokens: Optional[int] = None,
               **kwargs) -> Run:
        """Create a run.

        Args:
            thread_id (str): The thread to run.
            assistant_id (str): The assistant id to run.
            model (str): The model to use.
            instructions (str, optional): The system instructions this assistant uses. Defaults to None.
            additional_instructions (Optional[str], optional): Appends additional
                instructions at the end of the instructions for the run. This is
                useful for modifying the behavior on a per-run basis without
                overriding other instructions.. Defaults to None.
            tools (Optional[str], optional): List of tools to use.. Defaults to [].
            metadata (Dict, optional): Custom key-value pairs associate with run. Defaults to None.
            workspace (str): The DashScope workspace id.
            api_key (str, optional): The DashScope workspace id. Defaults to None.

        Raises:
            InputRequired: thread and assistant is required.

        Returns:
            Run: The `Run` object.
        """
        if not thread_id or not assistant_id:
            raise InputRequired('thread_id and assistant_id is required')
        data = {'assistant_id': assistant_id}
        if model:
            data['model'] = model
        if instructions:
            data['instructions'] = instructions
        if additional_instructions:
            data['additional_instructions'] = additional_instructions
        if tools:
            data['tools'] = tools
        if metadata:
            data['metadata'] = metadata
        data['stream'] = stream
        if extra_body is not None and extra_body:
            data = {**data, **extra_body}

        if top_p is not None:
            data['top_p'] = top_p
        if top_k is not None:
            data['top_k'] = top_k
        if temperature is not None:
            data['temperature'] = temperature
        if max_tokens is not None:
            data['max_tokens'] = max_tokens

        response = super().call(data=data,
                                path=f'threads/{thread_id}/runs',
                                api_key=api_key,
                                flattened_output=True,
                                stream=stream,
                                workspace=workspace,
                                **kwargs)
        if stream:
            return ((event_type, cls.convert_stream_object(event_type, item))
                    for event_type, item in response)
        else:
            return Run(**response)

    @classmethod
    def convert_stream_object(cls, event, item):
        event_object_map = {
            'thread.created': Thread,
            'thread.run.created': Run,
            'thread.run.queued': Run,
            'thread.run.in_progress': Run,
            'thread.run.requires_action': Run,
            'thread.run.completed': Run,
            'thread.run.failed': Run,
            'thread.run.cancelled': Run,
            'thread.run.expired': Run,
            'thread.run.step.created': RunStep,
            'thread.run.step.in_progress': RunStep,
            'thread.run.step.delta': RunStepDelta,
            'thread.run.step.completed': RunStep,
            'thread.run.step.failed': RunStep,
            'thread.run.step.cancelled': RunStep,
            'thread.run.step.expired': RunStep,
            'thread.message.created': ThreadMessage,
            'thread.message.in_progress': ThreadMessage,
            'thread.message.delta': ThreadMessageDelta,
            'thread.message.completed': ThreadMessage,
            'thread.message.incomplete': ThreadMessage,
            'error': AssistantError,
        }
        if (event in event_object_map):
            return event_object_map[event](**item)
        else:
            return item

    @classmethod
    def call(cls,
             thread_id: str,
             *,
             assistant_id: str,
             model: Optional[str] = None,
             instructions: Optional[str] = None,
             additional_instructions: Optional[str] = None,
             tools: Optional[List[Dict]] = None,
             stream: Optional[bool] = False,
             metadata: Optional[Dict] = None,
             workspace: str = None,
             extra_body: Optional[Dict] = None,
             api_key: str = None,
             top_p: Optional[float] = None,
             top_k: Optional[int] = None,
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None,
             **kwargs) -> Run:
        """Create a run.

        Args:
            thread_id (str): The thread to run.
            assistant_id (str): The assistant id to run.
            model (str): The model to use.
            instructions (str, optional): The system instructions this assistant uses. Defaults to None.
            additional_instructions (Optional[str], optional): Appends additional
                instructions at the end of the instructions for the run. This is
                useful for modifying the behavior on a per-run basis without
                overriding other instructions.. Defaults to None.
            tools (Optional[str], optional): List of tools to use.. Defaults to [].
            metadata (Dict, optional): Custom key-value pairs associate with run. Defaults to None.
            workspace (str): The DashScope workspace id.
            api_key (str, optional): The DashScope workspace id. Defaults to None.

        Raises:
            InputRequired: thread and assistant is required.

        Returns:
            Run: The `Run` object.
        """
        return cls.create(thread_id,
                          assistant_id=assistant_id,
                          model=model,
                          instructions=instructions,
                          additional_instructions=additional_instructions,
                          tools=tools,
                          stream=stream,
                          metadata=metadata,
                          workspace=workspace,
                          extra_body=extra_body,
                          api_key=api_key,
                          top_p=top_p,
                          top_k=top_k,
                          temperature=temperature,
                          max_tokens=max_tokens,
                          **kwargs)

    @classmethod
    def list(cls,
             thread_id: str,
             *,
             limit: int = None,
             order: str = None,
             after: str = None,
             before: str = None,
             workspace: str = None,
             api_key: str = None,
             **kwargs) -> RunList:
        """List `Run`.

        Args:
            thread_id (str): The thread id.
            limit (int, optional): How many assistant to retrieve. Defaults to None.
            order (str, optional): Sort order by created_at. Defaults to None.
            after (str, optional): Assistant id after. Defaults to None.
            before (str, optional): Assistant id before. Defaults to None.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            RunList: The list of runs.
        """
        if not thread_id:
            raise InputRequired('thread_id is required!')
        response = super().list(limit=limit,
                                order=order,
                                after=after,
                                before=before,
                                path=f'threads/{thread_id}/runs',
                                workspace=workspace,
                                api_key=api_key,
                                flattened_output=True,
                                **kwargs)
        return RunList(**response)

    @classmethod
    def retrieve(cls,
                 run_id: str,
                 *,
                 thread_id: str,
                 workspace: str = None,
                 api_key: str = None,
                 **kwargs) -> Run:
        """Retrieve the `Run`.

        Args:
            thread_id (str): The thread id.
            run_id (str): The run id.
            workspace (str): The dashscope workspace id.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            Run: The `Run` object.
        """
        if not thread_id or not run_id:
            raise InputRequired('thread_id and run_id are required!')
        response = super().get(run_id,
                               path=f'threads/{thread_id}/runs/{run_id}',
                               workspace=workspace,
                               api_key=api_key,
                               flattened_output=True,
                               **kwargs)
        return Run(**response)

    @classmethod
    def get(cls,
            run_id: str,
            *,
            thread_id: str,
            workspace: str = None,
            api_key: str = None,
            **kwargs) -> Run:
        """Retrieve the `Run`.

        Args:
            thread_id (str): The thread id.
            run_id (str): The run id.
            workspace (str): The dashscope workspace id.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            Run: The `Run` object.
        """
        return cls.retrieve(run_id,
                            thread_id=thread_id,
                            workspace=workspace,
                            api_key=api_key,
                            **kwargs)

    @classmethod
    def submit_tool_outputs(cls,
                            run_id: str,
                            *,
                            thread_id: str,
                            tool_outputs: List[Dict],
                            stream: Optional[bool] = False,
                            workspace: str = None,
                            extra_body: Optional[Dict] = None,
                            api_key: str = None,
                            **kwargs) -> Run:
        """_summary_

        Args:
            thread_id (str): The thread id.
            run_id (str): The run id.
            tool_outputs (List[Dict]): The tool outputs.
            workspace (str): The dashscope workspace id.
            api_key (str, optional): The api key. Defaults to None.

        Raises:
            InputRequired: The tool output thread id run id
                are required.

        Returns:
            Run: The 'Run`.
        """
        if not tool_outputs:
            raise InputRequired('tool_outputs is required!')
        if not thread_id or not run_id:
            raise InputRequired('thread_id and run_id are required!')

        data = {'tool_outputs': tool_outputs}
        data['stream'] = stream
        if extra_body is not None and extra_body:
            data = {**data, **extra_body}

        response = super().call(
            data,
            path=f'threads/{thread_id}/runs/{run_id}/submit_tool_outputs',
            workspace=workspace,
            api_key=api_key,
            stream=stream,
            flattened_output=True,
            **kwargs)
        if stream:
            return ((event_type, cls.convert_stream_object(event_type, item))
                    for event_type, item in response)
        else:
            return Run(**response)

    @classmethod
    def wait(cls,
             run_id: str,
             *,
             thread_id: str,
             timeout_seconds: float = float('inf'),
             workspace: str = None,
             api_key: str = None,
             **kwargs) -> Run:
        """Wait for run to complete.

        Args:
            thread_id (str): The thread id.
            run_id (str): The run id.
            timeout_seconds (int): The timeout seconds. Defaults inf.
            workspace (str): The dashscope workspace id.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            Run: The run final status.
        """
        if not run_id or not thread_id:
            raise InputRequired('run_id and thread_id are required!')
        start_time = time.perf_counter()
        while True:
            run = cls.get(run_id,
                          thread_id=thread_id,
                          workspace=workspace,
                          api_key=api_key)
            if run.status_code == HTTPStatus.OK:
                if hasattr(run, 'status'):
                    if run.status in [
                            'cancelled', 'failed', 'completed', 'expired',
                            'requires_action'
                    ]:
                        break
                    else:
                        time_eclipsed = time.perf_counter() - start_time
                        if time_eclipsed > timeout_seconds:
                            raise TimeoutException('Wait run complete timeout')
                        time.sleep(1)
                else:
                    logger.error('run has no status')
                    break
            else:
                logger.error(
                    'Get run thread_id: %s, run_id: %s failed, message: %s' %
                    (thread_id, run_id, run.message))
                break
        return run

    @classmethod
    def update(cls,
               run_id: str,
               *,
               thread_id: str,
               metadata: Optional[Dict] = None,
               workspace: str = None,
               api_key: str = None,
               **kwargs) -> Run:
        """Create a run.

        Args:
            thread_id (str): The thread of the run id to be updated.
            run_id (str): The run id to update.
            model (str): The model to use.
            metadata (Dict, optional): Custom key-value pairs associate with run. Defaults to None.
            workspace (str): The DashScope workspace id.
            api_key (str, optional): The DashScope workspace id. Defaults to None.

        Raises:
            InputRequired: thread id and run is required.

        Returns:
            Run: The `Run` object.
        """
        if not thread_id or not run_id:
            raise InputRequired('thread id and run id are required!')
        response = super().update(run_id,
                                  json={'metadata': metadata},
                                  path='threads/%s/runs/%s' %
                                  (thread_id, run_id),
                                  api_key=api_key,
                                  workspace=workspace,
                                  flattened_output=True,
                                  method='post',
                                  **kwargs)
        return Run(**response)

    @classmethod
    def cancel(cls,
               run_id: str,
               *,
               thread_id: str,
               workspace: str = None,
               api_key: str = None,
               **kwargs) -> Run:
        """Cancel the `Run`.

        Args:
            thread_id (str): The thread id.
            run_id (str): The run id.
            workspace (str): The dashscope workspace id.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            Run: The `Run` object.
        """
        if not thread_id or not run_id:
            raise InputRequired('thread id and run id are required!')
        response = super().cancel(run_id,
                                  path='threads/%s/runs/%s/cancel' %
                                  (thread_id, run_id),
                                  api_key=api_key,
                                  workspace=workspace,
                                  flattened_output=True,
                                  **kwargs)

        return Run(**response)
