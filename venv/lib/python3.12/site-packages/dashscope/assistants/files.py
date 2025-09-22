# Copyright (c) Alibaba, Inc. and its affiliates.
from typing import Optional

from dashscope.assistants.assistant_types import (AssistantFile,
                                                  AssistantFileList,
                                                  DeleteResponse)
from dashscope.client.base_api import (CreateMixin, DeleteMixin,
                                       GetStatusMixin, ListObjectMixin)
from dashscope.common.error import InputRequired

__all__ = ['Files']


class Files(CreateMixin, DeleteMixin, ListObjectMixin, GetStatusMixin):
    SUB_PATH = 'assistants'

    @classmethod
    def call(cls,
             assistant_id: str,
             *,
             file_id: str,
             workspace: str = None,
             api_key: str = None,
             **kwargs) -> AssistantFile:
        """Create assistant file.

        Args:
            assistant_id (str): The target assistant id.
            file_id (str): The file id.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): The DashScope api key. Defaults to None.

        Raises:
            InputRequired: The assistant id and file id are required.

        Returns:
            AssistantFile: The assistant file object.
        """
        return cls.create(assistant_id,
                          file_id=file_id,
                          workspace=workspace,
                          api_key=api_key,
                          **kwargs)

    @classmethod
    def create(cls,
               assistant_id: str,
               *,
               file_id: str,
               workspace: str = None,
               api_key: str = None,
               **kwargs) -> AssistantFile:
        """Create assistant file.

        Args:
            assistant_id (str): The target assistant id.
            file_id (str): The file id.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): The DashScope api key. Defaults to None.

        Raises:
            InputRequired: The assistant id and file id is required.

        Returns:
            AssistantFile: _description_
        """
        if not file_id or not assistant_id:
            raise InputRequired('input file_id and assistant_id is required!')

        response = super().call(data={'file_id': file_id},
                                path=f'assistants/{assistant_id}/files',
                                api_key=api_key,
                                flattened_output=True,
                                workspace=workspace,
                                **kwargs)
        return AssistantFile(**response)

    @classmethod
    def list(cls,
             assistant_id: str,
             *,
             limit: int = None,
             order: str = None,
             after: str = None,
             before: str = None,
             workspace: str = None,
             api_key: str = None,
             **kwargs) -> AssistantFileList:
        """List assistant files.

        Args:
            assistant_id (str): The assistant id.
            limit (int, optional): How many assistant to retrieve. Defaults to None.
            order (str, optional): Sort order by created_at. Defaults to None.
            after (str, optional): Assistant id after. Defaults to None.
            before (str, optional): Assistant id before. Defaults to None.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            ListAssistantFile: The list of file objects.
        """

        response = super().list(limit=limit,
                                order=order,
                                after=after,
                                before=before,
                                path=f'assistants/{assistant_id}/files',
                                api_key=api_key,
                                flattened_output=True,
                                workspace=workspace,
                                **kwargs)
        return AssistantFileList(**response)

    @classmethod
    def retrieve(cls,
                 file_id: str,
                 *,
                 assistant_id: str,
                 workspace: str = None,
                 api_key: str = None,
                 **kwargs) -> AssistantFile:
        """Retrieve file information.

        Args:
            file_id (str): The file if.
            assistant_id (str): The assistant id of the file.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            AssistantFile: The `AssistantFile` object.
        """
        if not assistant_id or not file_id:
            raise InputRequired('assistant id and file id are required!')
        response = super().get(
            file_id,
            path=f'assistants/{assistant_id}/files/{file_id}',
            api_key=api_key,
            flattened_output=True,
            workspace=workspace,
            **kwargs)
        return AssistantFile(**response)

    @classmethod
    def get(cls,
            file_id: str,
            *,
            assistant_id: str,
            workspace: str = None,
            api_key: str = None,
            **kwargs) -> Optional[AssistantFile]:
        """Retrieve file information.

        Args:
            file_id (str): The file if.
            assistant_id (str): The assistant id of the file.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            AssistantFile: The `AssistantFile` object.
        """
        response = super().get(target=assistant_id + '/files/' + file_id, api_key=api_key, workspace=workspace, **kwargs)
        if response.status_code == 200 and response.output:
            return AssistantFile(**response.output)
        else:
            return None

    @classmethod
    def delete(cls,
               file_id: str,
               *,
               assistant_id: str,
               workspace: str = None,
               api_key: str = None,
               **kwargs) -> DeleteResponse:
        """Delete the `file_id`.

        Args:
            file_id (str): The file to be deleted.
            assistant_id (str): The assistant id of the file.
            workspace (str, optional): The DashScope workspace id. Defaults to None.
            api_key (str, optional): Your DashScope api key. Defaults to None.

        Returns:
            AssistantsDeleteResponse: _description_
        """

        response = super().delete(
            file_id,
            path=f'assistants/{assistant_id}/files/{file_id}',
            api_key=api_key,
            flattened_output=True,
            workspace=workspace,
            **kwargs)
        return DeleteResponse(**response)
