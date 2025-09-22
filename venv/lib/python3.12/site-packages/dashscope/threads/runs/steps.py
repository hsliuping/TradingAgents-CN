# Copyright (c) Alibaba, Inc. and its affiliates.

from dashscope.client.base_api import GetStatusMixin, ListObjectMixin
from dashscope.common.error import InputRequired
from dashscope.threads.thread_types import RunStep, RunStepList

__all__ = ['Steps']


class Steps(ListObjectMixin, GetStatusMixin):
    SUB_PATH = 'RUNS'  # useless

    @classmethod
    def list(cls,
             run_id: str,
             *,
             thread_id: str,
             limit: int = None,
             order: str = None,
             after: str = None,
             before: str = None,
             workspace: str = None,
             api_key: str = None,
             **kwargs) -> RunStepList:
        """List  `RunStep` of `Run`.

        Args:
            thread_id (str): The thread id.
            run_id (str): The run id.
            limit (int, optional): How many assistant to retrieve. Defaults to None.
            order (str, optional): Sort order by created_at. Defaults to None.
            after (str, optional): Assistant id after. Defaults to None.
            before (str, optional): Assistant id before. Defaults to None.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            RunList: The list of runs.
        """
        if not run_id:
            raise InputRequired('run_id is required!')
        response = super().list(
            limit=limit,
            order=order,
            after=after,
            before=before,
            path=f'threads/{thread_id}/runs/{run_id}/steps',
            workspace=workspace,
            api_key=api_key,
            flattened_output=True,
            **kwargs)
        return RunStepList(**response)

    @classmethod
    def retrieve(cls,
                 step_id: str,
                 *,
                 thread_id: str,
                 run_id: str,
                 workspace: str = None,
                 api_key: str = None,
                 **kwargs) -> RunStep:
        """Retrieve the `RunStep`.

        Args:
            thread_id (str): The thread id.
            run_id (str): The run id.
            step_id (str): The step id.
            workspace (str): The dashscope workspace id.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            RunStep: The `RunStep` object.
        """
        if not thread_id or not run_id or not step_id:
            raise InputRequired('thread_id, run_id and step_id are required!')
        response = super().get(
            run_id,
            path=f'threads/{thread_id}/runs/{run_id}/steps/{step_id}',
            workspace=workspace,
            api_key=api_key,
            flattened_output=True,
            **kwargs)
        return RunStep(**response)

    @classmethod
    def get(cls,
            step_id: str,
            *,
            thread_id: str,
            run_id: str,
            workspace: str = None,
            api_key: str = None,
            **kwargs) -> RunStep:
        """Retrieve the `RunStep`.

        Args:
            thread_id (str): The thread id.
            run_id (str): The run id.
            step_id (str): The step id.
            workspace (str): The dashscope workspace id.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            RunStep: The `RunStep` object.
        """
        return cls.retrieve(thread_id,
                            run_id,
                            step_id,
                            workspace=workspace,
                            api_key=api_key,
                            **kwargs)
