# Copyright (c) Alibaba, Inc. and its affiliates.

from dataclasses import dataclass
from typing import List

from dashscope.api_entities.dashscope_response import (DashScopeAPIResponse,
                                                       DictMixin)
from dashscope.client.base_api import BaseApi
from dashscope.common.error import InputRequired, ModelRequired
from dashscope.common.utils import _get_task_group_and_task
from dashscope.utils.oss_utils import preprocess_message_element


@dataclass(init=False)
class MultiModalEmbeddingItemBase(DictMixin):
    factor: float

    def __init__(self, factor: float, **kwargs):
        super().__init__(factor=factor, **kwargs)


@dataclass(init=False)
class MultiModalEmbeddingItemText(MultiModalEmbeddingItemBase):
    text: str

    def __init__(self, text: str, factor: float, **kwargs):
        super().__init__(factor, **kwargs)
        self.text = text


@dataclass(init=False)
class MultiModalEmbeddingItemImage(MultiModalEmbeddingItemBase):
    image: str

    def __init__(self, image: str, factor: float, **kwargs):
        super().__init__(factor, **kwargs)
        self.image = image


@dataclass(init=False)
class MultiModalEmbeddingItemAudio(MultiModalEmbeddingItemBase):
    audio: str

    def __init__(self, audio: str, factor: float, **kwargs):
        super().__init__(factor, **kwargs)
        self.audio = audio


class MultiModalEmbedding(BaseApi):
    task = 'multimodal-embedding'

    class Models:
        multimodal_embedding_one_peace_v1 = 'multimodal-embedding-one-peace-v1'

    @classmethod
    def call(cls,
             model: str,
             input: List[MultiModalEmbeddingItemBase],
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> DashScopeAPIResponse:
        """Get embedding multimodal contents..

        Args:
            model (str): The embedding model name.
            input (List[MultiModalEmbeddingElement]): The embedding elements,
                every element include data, modal, factor field.
            workspace (str): The dashscope workspace id.
            **kwargs:
                auto_truncation(bool, `optional`): Automatically truncate
                audio longer than 15 seconds or text longer than 70 words.
                Default to false(Too long input will result in failure).

        Returns:
            DashScopeAPIResponse: The embedding result.
        """
        if input is None or not input:
            raise InputRequired('prompt is required!')
        if model is None or not model:
            raise ModelRequired('Model is required!')
        embedding_input = {}
        has_upload = cls._preprocess_message_inputs(model, input, api_key)
        if has_upload:
            headers = kwargs.pop('headers', {})
            headers['X-DashScope-OssResourceResolve'] = 'enable'
            kwargs['headers'] = headers
        embedding_input['contents'] = input
        kwargs.pop('stream', False)  # not support streaming output.
        task_group, function = _get_task_group_and_task(__name__)
        return super().call(model=model,
                            input=embedding_input,
                            task_group=task_group,
                            task=MultiModalEmbedding.task,
                            function=function,
                            api_key=api_key,
                            workspace=workspace,
                            **kwargs)

    @classmethod
    def _preprocess_message_inputs(cls, model: str, input: List[dict],
                                   api_key: str):
        """preprocess following inputs
        input = [{'factor': 1, 'text': 'hello'},
                {'factor': 2, 'audio': ''},
                {'factor': 3, 'image': ''}]
        """
        has_upload = False
        for elem in input:
            if not isinstance(elem, (int, float, bool, str, bytes, bytearray)):
                is_upload = preprocess_message_element(model, elem, api_key)
                if is_upload and not has_upload:
                    has_upload = True
        return has_upload
