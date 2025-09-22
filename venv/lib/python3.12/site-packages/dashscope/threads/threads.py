# Copyright (c) Alibaba, Inc. and its affiliates.

from typing import Dict, List, Optional

from dashscope.assistants.assistant_types import DeleteResponse
from dashscope.client.base_api import (CreateMixin, DeleteMixin,
                                       GetStatusMixin, UpdateMixin)
from dashscope.common.error import InputRequired
from dashscope.threads.thread_types import Run, Thread

__all__ = ['Threads']


class Threads(CreateMixin, DeleteMixin, GetStatusMixin, UpdateMixin):
    SUB_PATH = 'threads'

    @classmethod
    def call(cls,
             *,
             messages: List[Dict] = None,
             metadata: Dict = None,
             workspace: str = None,
             api_key: str = None,
             **kwargs) -> Thread:
        """Create a thread.

        Args:
            messages (List[Dict], optional): List of messages to start thread. Defaults to None.
            metadata (Dict, optional): The key-value information associate with thread. Defaults to None.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            Thread: The thread object.
        """
        return cls.create(messages=messages,
                          metadata=metadata,
                          workspace=workspace,
                          api_key=api_key,
                          **kwargs)

    @classmethod
    def create(cls,
               *,
               messages: List[Dict] = None,
               metadata: Dict = None,
               workspace: str = None,
               api_key: str = None,
               **kwargs) -> Thread:
        """Create a thread.

        Args:
            messages (List[Dict], optional): List of messages to start thread. Defaults to None.
            metadata (Dict, optional): The key-value information associate with thread. Defaults to None.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            Thread: The thread object.
        """
        data = {}
        if messages:
            data['messages'] = messages
        if metadata:
            data['metadata'] = metadata
        response = super().call(data=data if data else '',
                                api_key=api_key,
                                flattened_output=True,
                                workspace=workspace,
                                **kwargs)
        return Thread(**response)

    @classmethod
    def get(cls,
            thread_id: str,
            *,
            workspace: str = None,
            api_key: str = None,
            **kwargs) -> Thread:
        """Retrieve the thread.

        Args:
            thread_id (str): The target thread.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            Thread: The `Thread` information.
        """
        return cls.retrieve(thread_id,
                            workspace=workspace,
                            api_key=api_key,
                            **kwargs)

    @classmethod
    def retrieve(cls,
                 thread_id: str,
                 *,
                 workspace: str = None,
                 api_key: str = None,
                 **kwargs) -> Thread:
        """Retrieve the thread.

        Args:
            thread_id (str): The target thread.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            Thread: The `Thread` information.
        """
        if not thread_id:
            raise InputRequired('thread_id is required!')
        response = super().get(thread_id,
                               api_key=api_key,
                               flattened_output=True,
                               workspace=workspace,
                               **kwargs)
        return Thread(**response)

    @classmethod
    def update(cls,
               thread_id: str,
               *,
               metadata: Dict = None,
               workspace: str = None,
               api_key: str = None,
               **kwargs) -> Thread:
        """Update thread information.

        Args:
            thread_id (str): The thread id.
            metadata (Dict, optional): The thread key-value information. Defaults to None.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            Thread: The `Thread` information.
        """
        if not thread_id:
            raise InputRequired('thread_id is required!')
        response = super().update(thread_id,
                                  json={'metadata': metadata},
                                  api_key=api_key,
                                  workspace=workspace,
                                  flattened_output=True,
                                  method='post',
                                  **kwargs)
        return Thread(**response)

    @classmethod
    def delete(cls,
               thread_id,
               *,
               workspace: str = None,
               api_key: str = None,
               **kwargs) -> DeleteResponse:
        """Delete thread.

        Args:
            thread_id (str): The thread id to delete.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            AssistantsDeleteResponse: The deleted information.
        """
        if not thread_id:
            raise InputRequired('thread_id is required!')
        response = super().delete(thread_id,
                                  api_key=api_key,
                                  workspace=workspace,
                                  flattened_output=True,
                                  **kwargs)
        return DeleteResponse(**response)

    @classmethod
    def create_and_run(cls,
                       *,
                       assistant_id: str,
                       thread: Optional[Dict] = None,
                       model: Optional[str] = None,
                       instructions: Optional[str] = None,
                       additional_instructions: Optional[str] = None,
                       tools: Optional[List[Dict]] = None,
                       metadata: Optional[Dict] = None,
                       workspace: str = None,
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

        response = super().call(data=data,
                                path='threads/runs',
                                api_key=api_key,
                                flattened_output=True,
                                workspace=workspace,
                                **kwargs)
        return Run(**response)
