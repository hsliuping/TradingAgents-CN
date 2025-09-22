# Copyright (c) Alibaba, Inc. and its affiliates.

from typing import Union

from dashscope.api_entities.dashscope_response import DashScopeAPIResponse
from dashscope.client.base_api import BaseAsyncApi
from dashscope.common.error import InputRequired
from dashscope.common.utils import _get_task_group_and_task
from dashscope.embeddings.batch_text_embedding_response import \
    BatchTextEmbeddingResponse


class BatchTextEmbedding(BaseAsyncApi):
    task = 'text-embedding'
    function = 'text-embedding'
    """API for async text embedding.
    """
    class Models:
        text_embedding_async_v1 = 'text-embedding-async-v1'
        text_embedding_async_v2 = 'text-embedding-async-v2'

    @classmethod
    def call(cls,
             model: str,
             url: str,
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> BatchTextEmbeddingResponse:
        """Call async text embedding service and get result.

        Args:
            model (str): The model, reference ``Models``.
            url (Any): The async request file url, which contains text
                to embedding line by line.
            api_key (str, optional): The api api_key. Defaults to None.
            workspace (str): The dashscope workspace id.
            **kwargs:
                text_type(str, `optional`): [query|document], After the
                text is converted into a vector, it can be applied to
                downstream tasks such as retrieval, clustering, and
                classification. For asymmetric tasks such as retrieval,
                in order to achieve better retrieval results, it is
                recommended to distinguish between query text (query)
                and bottom database text (document) types, clustering
                Symmetric tasks such as , classification, etc. do not
                need to be specially specified, and the system
                default value "document" can be used
        Raises:
            InputRequired: The url cannot be empty.

        Returns:
            AsyncTextEmbeddingResponse: The async text embedding task result.
        """
        return super().call(model,
                            url,
                            api_key=api_key,
                            workspace=workspace,
                            **kwargs)

    @classmethod
    def async_call(cls,
                   model: str,
                   url: str,
                   api_key: str = None,
                   workspace: str = None,
                   **kwargs) -> BatchTextEmbeddingResponse:
        """Create a async text embedding task, and return task information.

        Args:
            model (str): The model, reference ``Models``.
            url (Any): The async request file url, which contains text
                to embedding line by line.
            api_key (str, optional): The api api_key. Defaults to None.
            workspace (str): The dashscope workspace id.
            **kwargs:
                text_type(str, `optional`): [query|document], After the
                text is converted into a vector, it can be applied to
                downstream tasks such as retrieval, clustering, and
                classification. For asymmetric tasks such as retrieval,
                in order to achieve better retrieval results, it is
                recommended to distinguish between query text (query)
                and bottom database text (document) types, clustering
                Symmetric tasks such as , classification, etc. do not
                need to be specially specified, and the system
                default value "document" can be used

        Raises:
            InputRequired: The url cannot be empty.

        Returns:
            DashScopeAPIResponse: The image synthesis
                task id in the response.
        """
        if url is None or not url:
            raise InputRequired('url is required!')
        input = {'url': url}
        task_group, _ = _get_task_group_and_task(__name__)
        response = super().async_call(model=model,
                                      task_group=task_group,
                                      task=BatchTextEmbedding.task,
                                      function=BatchTextEmbedding.function,
                                      api_key=api_key,
                                      input=input,
                                      workspace=workspace,
                                      **kwargs)
        return BatchTextEmbeddingResponse.from_api_response(response)

    @classmethod
    def fetch(cls,
              task: Union[str, BatchTextEmbeddingResponse],
              api_key: str = None,
              workspace: str = None) -> BatchTextEmbeddingResponse:
        """Fetch async text embedding task status or result.

        Args:
            task (Union[str, AsyncTextEmbeddingResponse]): The task_id or
                AsyncTextEmbeddingResponse return by async_call().
            api_key (str, optional): The api api_key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            AsyncTextEmbeddingResponse: The task status or result.
        """
        response = super().fetch(task, api_key, workspace=workspace)
        return BatchTextEmbeddingResponse.from_api_response(response)

    @classmethod
    def wait(cls,
             task: Union[str, BatchTextEmbeddingResponse],
             api_key: str = None,
             workspace: str = None) -> BatchTextEmbeddingResponse:
        """Wait for async text embedding task to complete, and return the result.

        Args:
            task (Union[str, AsyncTextEmbeddingResponse]): The task_id or
                AsyncTextEmbeddingResponse return by async_call().
            api_key (str, optional): The api api_key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            AsyncTextEmbeddingResponse: The task result.
        """
        response = super().wait(task, api_key, workspace=workspace)
        return BatchTextEmbeddingResponse.from_api_response(response)

    @classmethod
    def cancel(cls,
               task: Union[str, BatchTextEmbeddingResponse],
               api_key: str = None,
               workspace: str = None) -> DashScopeAPIResponse:
        """Cancel async text embedding task.
        Only tasks whose status is PENDING can be canceled.

        Args:
            task (Union[str, AsyncTextEmbeddingResponse]): The task_id or
                AsyncTextEmbeddingResponse return by async_call().
            api_key (str, optional): The api api_key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            DashScopeAPIResponse: The response data.
        """
        return super().cancel(task, api_key, workspace=workspace)

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
            model_name (str, optional): The tasks model name. Defaults to None.
            api_key_id (str, optional): The tasks api-key-id. Defaults to None.
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
        return super().list(start_time=start_time,
                            end_time=end_time,
                            model_name=model_name,
                            api_key_id=api_key_id,
                            region=region,
                            status=status,
                            page_no=page_no,
                            page_size=page_size,
                            api_key=api_key,
                            workspace=workspace,
                            **kwargs)
