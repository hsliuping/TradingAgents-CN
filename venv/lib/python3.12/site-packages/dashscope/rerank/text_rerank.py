# Copyright (c) Alibaba, Inc. and its affiliates.

from typing import List

from dashscope.api_entities.dashscope_response import ReRankResponse
from dashscope.client.base_api import BaseApi
from dashscope.common.error import InputRequired, ModelRequired
from dashscope.common.utils import _get_task_group_and_task


class TextReRank(BaseApi):
    task = 'text-rerank'
    """API for rerank models.

    """
    class Models:
        gte_rerank = 'gte-rerank'

    @classmethod
    def call(cls,
             model: str,
             query: str,
             documents: List[str],
             return_documents: bool = None,
             top_n: int = None,
             api_key: str = None,
             **kwargs) -> ReRankResponse:
        """Calling rerank service.

        Args:
            model (str): The model to use.
            query (str): The query string.
            documents (List[str]): The documents to rank.
            return_documents(bool, `optional`): enable return origin documents,
                system default is false.
            top_n(int, `optional`): how many documents to return, default return
                all the documents.
            api_key (str, optional): The DashScope api key. Defaults to None.

        Raises:
            InputRequired: The query and documents are required.
            ModelRequired: The model is required.

        Returns:
            RerankResponse: The rerank result.
        """

        if query is None or documents is None or not documents:
            raise InputRequired('query and documents are required!')
        if model is None or not model:
            raise ModelRequired('Model is required!')
        task_group, function = _get_task_group_and_task(__name__)
        input = {'query': query, 'documents': documents}
        parameters = {}
        if return_documents is not None:
            parameters['return_documents'] = return_documents
        if top_n is not None:
            parameters['top_n'] = top_n
        parameters = {**parameters, **kwargs}

        response = super().call(model=model,
                                task_group=task_group,
                                task=TextReRank.task,
                                function=function,
                                api_key=api_key,
                                input=input,
                                **parameters)

        return ReRankResponse.from_api_response(response)
