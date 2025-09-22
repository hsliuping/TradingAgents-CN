# Copyright (c) Alibaba, Inc. and its affiliates.

from dashscope.api_entities.dashscope_response import DashScopeAPIResponse
from dashscope.client.base_api import BaseApi
from dashscope.common.error import InputRequired, ModelRequired
from dashscope.common.logging import logger
from dashscope.common.utils import _get_task_group_and_task


class Understanding(BaseApi):
    nlu_task = 'nlu'
    """API for AI-Generated Content(AIGC) models.

    """
    class Models:
        opennlu_v1 = 'opennlu-v1'

    @classmethod
    def call(cls,
             model: str,
             sentence: str = None,
             labels: str = None,
             task: str = None,
             api_key: str = None,
             **kwargs) -> DashScopeAPIResponse:
        """Call generation model service.

        Args:
            model (str): The requested model, such as opennlu-v1
            sentence (str): The text content entered by the user that needs to be processed supports both Chinese and English. (The maximum limit for input is 1024 tokens, which is the sum of all input fields).  # noqa E501
            labels (list): For the extraction task, label is the name of the type that needs to be extracted. For classification tasks, label is the classification system. Separate different labels with Chinese commas..  # noqa E501
            task (str): Task type, optional as extraction or classification, default as extraction.
            api_key (str, optional): The api api_key, can be None,
                if None, will get by default rule(TODO: api key doc).

        Returns:
            DashScopeAPIResponse: The understanding result.
        """
        if (sentence is None or not sentence) or (labels is None
                                                  or not labels):
            raise InputRequired('sentence and labels is required!')
        if model is None or not model:
            raise ModelRequired('Model is required!')
        if kwargs.pop('stream', False):  # not support stream
            logger.warning('stream option not supported for Understanding.')
        task_group, function = _get_task_group_and_task(__name__)
        input, parameters = cls._build_input_parameters(
            model, sentence, labels, task, **kwargs)
        return super().call(model=model,
                            task_group=task_group,
                            task=Understanding.nlu_task,
                            function=function,
                            api_key=api_key,
                            input=input,
                            **parameters)

    @classmethod
    def _build_input_parameters(cls, model, sentence, labels, task, **kwargs):
        parameters = {}
        input = {'sentence': sentence, 'labels': labels}
        if task is not None and task:
            input['task'] = task

        return input, {**parameters, **kwargs}
