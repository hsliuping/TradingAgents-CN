# Copyright (c) Alibaba, Inc. and its affiliates.

from dashscope.client.base_api import GetStatusMixin, ListObjectMixin
from dashscope.common.error import InputRequired
from dashscope.threads.thread_types import MessageFile, MessageFileList

__all__ = ['Files']


class Files(ListObjectMixin, GetStatusMixin):
    SUB_PATH = 'messages'  # useless

    @classmethod
    def retrieve(cls,
                 file_id: str,
                 *,
                 thread_id: str,
                 message_id: str,
                 workspace: str = None,
                 api_key: str = None,
                 **kwargs) -> MessageFile:
        """Retrieve the `MessageFile`.

        Args:
            thread_id (str): The thread id.
            message_id (str): The message id.
            file_id (str): The file id.
            workspace (str): The dashscope workspace id.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            MessageFile: The `MessageFile` object.
        """
        return cls.get(file_id,
                       thread_id=thread_id,
                       message_id=message_id,
                       workspace=workspace,
                       api_key=api_key,
                       **kwargs)

    @classmethod
    def get(cls,
            file_id: str,
            *,
            message_id: str,
            thread_id: str,
            workspace: str = None,
            api_key: str = None,
            **kwargs) -> MessageFile:
        """Retrieve the `MessageFile`.

        Args:
            assistant_id (str): The assistant id.
            message_id (str): The message id.
            file_id (str): The file id.
            workspace (str): The dashscope workspace id.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            MessageFile: The `MessageFile` object.
        """
        if not thread_id or not message_id or not file_id:
            raise InputRequired(
                'thread id, message id and file id are required!')
        response = super().get(
            message_id,
            path=f'threads/{thread_id}/messages/{message_id}/files/{file_id}',
            workspace=workspace,
            api_key=api_key,
            flattened_output=True,
            **kwargs)
        return MessageFile(**response)

    @classmethod
    def list(cls,
             message_id: str,
             *,
             thread_id: str,
             limit: int = None,
             order: str = None,
             after: str = None,
             before: str = None,
             workspace: str = None,
             api_key: str = None,
             **kwargs) -> MessageFileList:
        """List message files.

        Args:
            thread_id (str): The thread id.
            message_id (str): The message_id.
            limit (int, optional): How many assistant to retrieve. Defaults to None.
            order (str, optional): Sort order by created_at. Defaults to None.
            after (str, optional): Assistant id after. Defaults to None.
            before (str, optional): Assistant id before. Defaults to None.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            MessageFileList: The `MessageFileList`.
        """
        if not thread_id or not message_id:
            raise InputRequired('thread id, message id are required!')
        response = super().list(
            limit=limit,
            order=order,
            after=after,
            before=before,
            path=f'threads/{thread_id}/messages/{message_id}/files',
            workspace=workspace,
            api_key=api_key,
            flattened_output=True,
            **kwargs)
        return MessageFileList(**response)
