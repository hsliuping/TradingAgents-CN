# Copyright (c) Alibaba, Inc. and its affiliates.

from typing import Dict, List, Optional

from dashscope.client.base_api import (CreateMixin, GetStatusMixin,
                                       ListObjectMixin, UpdateMixin)
from dashscope.common.error import InputRequired
from dashscope.threads.thread_types import ThreadMessage, ThreadMessageList

__all__ = ['Messages']


class Messages(CreateMixin, ListObjectMixin, GetStatusMixin, UpdateMixin):
    SUB_PATH = 'messages'  # useless

    @classmethod
    def call(cls,
             thread_id: str,
             *,
             content: str,
             role: str = 'user',
             file_ids: List[str] = [],
             metadata: Optional[object] = None,
             workspace: str = None,
             api_key: str = None,
             **kwargs) -> ThreadMessage:
        """Create message of thread.

        Args:
            thread_id (str): The thread id.
            content (str): The message content.
            role (str, optional): The message role. Defaults to 'user'.
            file_ids (List[str], optional): The file_ids include in message. Defaults to [].
            metadata (Optional[object], optional): The custom key/value pairs. Defaults to None.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): The DashScope api key. Defaults to None.

        Returns:
            ThreadMessage: The `ThreadMessage` object.
        """
        return cls.create(thread_id,
                          content=content,
                          role=role,
                          file_ids=file_ids,
                          metadata=metadata,
                          workspace=workspace,
                          **kwargs)

    @classmethod
    def create(cls,
               thread_id: str,
               *,
               content: str,
               role: str = 'user',
               file_ids: List[str] = [],
               metadata: Optional[object] = None,
               workspace: str = None,
               api_key: str = None,
               **kwargs) -> ThreadMessage:
        """Create message of thread.

        Args:
            thread_id (str): The thread id.
            content (str): The message content.
            role (str, optional): The message role. Defaults to 'user'.
            file_ids (List[str], optional): The file_ids include in message. Defaults to [].
            metadata (Optional[object], optional): The custom key/value pairs. Defaults to None.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): The DashScope api key. Defaults to None.

        Returns:
            ThreadMessage: The `ThreadMessage` object.
        """
        cls.SUB_PATH = '%s/messages' % thread_id
        data = {}
        if not thread_id or not content:
            raise InputRequired('thread_id and content are required!')
        data['content'] = content
        data['role'] = role
        if metadata:
            data['metadata'] = metadata
        if file_ids:
            data['file_ids'] = file_ids
        response = super().call(data=data,
                                path=f'threads/{thread_id}/messages',
                                api_key=api_key,
                                flattened_output=True,
                                workspace=workspace,
                                **kwargs)
        return ThreadMessage(**response)

    @classmethod
    def retrieve(cls,
                 message_id: str,
                 *,
                 thread_id: str,
                 workspace: str = None,
                 api_key: str = None,
                 **kwargs) -> ThreadMessage:
        """Get the `ThreadMessage`.

        Args:
            thread_id (str): The thread id.
            message_id (str): The message id.
            workspace (str): The dashscope workspace id.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            ThreadMessage: The `ThreadMessage` object.
        """
        return cls.get(message_id,
                       thread_id=thread_id,
                       workspace=workspace,
                       api_key=api_key,
                       **kwargs)

    @classmethod
    def get(cls,
            message_id: str,
            *,
            thread_id: str,
            workspace: str = None,
            api_key: str = None,
            **kwargs) -> ThreadMessage:
        """Get the `ThreadMessage`.

        Args:
            thread_id (str): The thread id.
            message_id (str): The message id.
            workspace (str): The dashscope workspace id.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            ThreadMessage: The `ThreadMessage` object.
        """
        if not message_id or not thread_id:
            raise InputRequired('thread id, message id are required!')
        response = super().get(
            message_id,
            path=f'threads/{thread_id}/messages/{message_id}',
            workspace=workspace,
            api_key=api_key,
            flattened_output=True,
            **kwargs)
        return ThreadMessage(**response)

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
             **kwargs) -> ThreadMessageList:
        """List message of the thread.

        Args:
            thread_id (str): The thread id.
            limit (int, optional): How many assistant to retrieve. Defaults to None.
            order (str, optional): Sort order by created_at. Defaults to None.
            after (str, optional): Assistant id after. Defaults to None.
            before (str, optional): Assistant id before. Defaults to None.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            ThreadMessageList: The `ThreadMessageList` object.
        """
        if not thread_id:
            raise InputRequired('thread id is required!')
        response = super().list(limit=limit,
                                order=order,
                                after=after,
                                before=before,
                                path=f'threads/{thread_id}/messages',
                                workspace=workspace,
                                api_key=api_key,
                                flattened_output=True,
                                **kwargs)
        return ThreadMessageList(**response)

    @classmethod
    def update(cls,
               message_id: str,
               *,
               thread_id: str,
               metadata: Dict = None,
               workspace: str = None,
               api_key: str = None,
               **kwargs) -> ThreadMessage:
        """Update an message of the thread.

        Args:
            thread_id (str): The thread id.
            message_id (str): The message id.
            content (str): The message content.
            role (str, optional): The message role. Defaults to 'user'.
            file_ids (List[str], optional): The file_ids include in message. Defaults to [].
            metadata (Optional[object], optional): The custom key/value pairs. Defaults to None.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): The DashScope api key. Defaults to None.

        Returns:
            ThreadMessage: The `ThreadMessage` object.
        """
        if not thread_id or not message_id:
            raise InputRequired('thread id and message id are required!')
        response = super().update(target=message_id,
                                  json={'metadata': metadata},
                                  path='threads/%s/messages/%s' %
                                  (thread_id, message_id),
                                  api_key=api_key,
                                  workspace=workspace,
                                  flattened_output=True,
                                  method='post',
                                  **kwargs)
        return ThreadMessage(**response)
