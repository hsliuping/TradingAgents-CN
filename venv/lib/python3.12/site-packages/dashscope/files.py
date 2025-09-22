# Copyright (c) Alibaba, Inc. and its affiliates.

import os

from dashscope.api_entities.dashscope_response import DashScopeAPIResponse
from dashscope.client.base_api import (DeleteMixin, FileUploadMixin, GetMixin,
                                       ListMixin)
from dashscope.common.constants import FilePurpose
from dashscope.common.error import InvalidFileFormat
from dashscope.common.utils import is_validate_fine_tune_file


class Files(FileUploadMixin, ListMixin, DeleteMixin, GetMixin):
    SUB_PATH = 'files'

    @classmethod
    def upload(cls,
               file_path: str,
               purpose: str = FilePurpose.fine_tune,
               description: str = None,
               api_key: str = None,
               workspace: str = None,
               **kwargs) -> DashScopeAPIResponse:
        """Upload file for model fine-tune or other tasks.

        Args:
            file_path (str): The local file name to upload.
            purpose (str): The purpose of the file[fine-tune|inference]
            description (str, optional): The file description message.
            api_key (str, optional): The api key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            DashScopeAPIResponse: The upload information
        """
        if purpose == FilePurpose.fine_tune:
            if not is_validate_fine_tune_file(file_path):
                raise InvalidFileFormat(
                    'The file %s is not in valid jsonl format' % file_path)
        with open(file_path, 'rb') as f:
            return super().upload(files=[('files', (os.path.basename(f.name),
                                                    f, None))],
                                  descriptions=[description]
                                  if description is not None else None,
                                  api_key=api_key,
                                  workspace=workspace,
                                  **kwargs)

    @classmethod
    def list(cls,
             page=1,
             page_size=10,
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> DashScopeAPIResponse:
        """List uploaded files.

        Args:
            api_key (str, optional):
            The api api_key, can be None,
                if None, will get by default rule(TODO: api key doc).
            page (int, optional): Page number. Defaults to 1.
            page_size (int, optional): Items per page. Defaults to 10.
            workspace (str): The dashscope workspace id.

        Returns:
            DashScopeAPIResponse: The fine-tune jobs in the result.
        """
        return super().list(page,
                            page_size,
                            api_key,
                            workspace=workspace,
                            **kwargs)

    @classmethod
    def get(cls,
            file_id: str,
            api_key: str = None,
            workspace: str = None,
            **kwargs) -> DashScopeAPIResponse:
        """Get the file info.

        Args:
            file_id (str): The file id.
            api_key (str, optional): The api key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            DashScopeAPIResponse: The job info
        """
        return super().get(file_id, api_key, workspace=workspace, **kwargs)

    @classmethod
    def delete(cls,
               file_id: str,
               api_key: str = None,
               workspace: str = None,
               **kwargs) -> DashScopeAPIResponse:
        """Delete uploaded file.

        Args:
            file_id (str): The file id want to delete.
            api_key (str, optional): The api key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            DashScopeAPIResponse: Delete result.
        """
        return super().delete(file_id, api_key, workspace=workspace, **kwargs)
