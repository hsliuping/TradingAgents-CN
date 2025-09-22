# Copyright (c) Alibaba, Inc. and its affiliates.

from typing import List, Union

from dashscope.api_entities.dashscope_response import DashScopeAPIResponse
from dashscope.client.base_api import BaseApi
from dashscope.common.constants import TEXT_EMBEDDING_INPUT_KEY
from dashscope.common.utils import _get_task_group_and_task


class TextEmbedding(BaseApi):
    task = 'text-embedding'

    class Models:
        text_embedding_v1 = 'text-embedding-v1'
        text_embedding_v2 = 'text-embedding-v2'
        text_embedding_v3 = 'text-embedding-v3'
        text_embedding_v4 = 'text-embedding-v4'

    @classmethod
    def call(cls,
             model: str,
             input: Union[str, List[str]],
             workspace: str = None,
             api_key: str = None,
             **kwargs) -> DashScopeAPIResponse:
        """Get embedding of text input.

        Args:
            model (str): The embedding model name.
            input (Union[str, List[str], io.IOBase]): The text input,
                can be a text or list of text or opened file object,
                if opened file object, will read all lines,
                one embedding per line.
            workspace (str): The dashscope workspace id.
            **kwargs:
                text_type(str, `optional`): query or document.

        Returns:
            DashScopeAPIResponse: The embedding result.
        """
        embedding_input = {}
        if isinstance(input, str):
            embedding_input[TEXT_EMBEDDING_INPUT_KEY] = [input]
        else:
            embedding_input[TEXT_EMBEDDING_INPUT_KEY] = input
        kwargs.pop('stream', False)  # not support streaming output.
        task_group, function = _get_task_group_and_task(__name__)
        return super().call(model=model,
                            input=embedding_input,
                            task_group=task_group,
                            task=TextEmbedding.task,
                            function=function,
                            api_key=api_key,
                            workspace=workspace,
                            **kwargs)
