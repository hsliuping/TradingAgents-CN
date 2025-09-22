# Copyright (c) Alibaba, Inc. and its affiliates.

import copy
from typing import Any, List

from dashscope.api_entities.dashscope_response import (DashScopeAPIResponse,
                                                       Message, Role)
from dashscope.client.base_api import BaseApi
from dashscope.common.constants import (CUSTOMIZED_MODEL_ID,
                                        DEPRECATED_MESSAGE, HISTORY, MESSAGES,
                                        PROMPT)
from dashscope.common.error import InputRequired, ModelRequired
from dashscope.common.logging import logger


class Tokenization(BaseApi):
    FUNCTION = 'tokenizer'
    """API for get tokenizer result..

    """
    class Models:
        """List of models currently supported
        """
        qwen_turbo = 'qwen-turbo'
        qwen_plus = 'qwen-plus'
        qwen_7b_chat = 'qwen-7b-chat'
        qwen_14b_chat = 'qwen-14b-chat'
        llama2_7b_chat_v2 = 'llama2-7b-chat-v2'
        llama2_13b_chat_v2 = 'llama2-13b-chat-v2'
        text_embedding_v2 = 'text-embedding-v2'
        qwen_72b_chat = 'qwen-72b-chat'

    @classmethod
    def call(cls,
             model: str,
             input: Any = None,
             prompt: Any = None,
             history: list = None,
             api_key: str = None,
             messages: List[Message] = None,
             workspace: str = None,
             **kwargs) -> DashScopeAPIResponse:
        """Call tokenization.

        Args:
            model (str): The requested model, such as qwen-v1
            input: (Any): The model input body.
            prompt (Any): The input prompt, for qwen serial model.
            history (list):The user provided history,
                deprecated, use messages instead.
                examples:
                    [{'user':'The weather is fine today.',
                    'bot': 'Suitable for outings'}].
                Defaults to None.
            api_key (str, optional): The api api_key, can be None,
                if None, will get by default rule(TODO: api key doc).
            messages (list): The generation messages.
                examples:
                    [{'role': 'user',
                      'content': 'The weather is fine today.'},
                      {'role': 'assistant', 'content': 'Suitable for outings'}]
            workspace (str): The dashscope workspace id.
            **kwargs:
                see model input.

        Raises:
            InputRequired: input is required.
            ModelRequired: model is required.

        Returns:
            DashScopeAPIResponse: The tokenizer output.
        """
        if (input is None or not input) and \
            (prompt is None or not prompt) and \
                (messages is None or not messages):
            raise InputRequired('prompt or messages is required!')
        if model is None or not model:
            raise ModelRequired('Model is required!')
        if input is None:
            input, parameters = cls._build_llm_parameters(
                model, prompt, history, messages, **kwargs)
        else:
            parameters = kwargs

        if kwargs.pop('stream', False):  # not support stream
            logger.warning('streaming option not supported for tokenization.')

        return super().call(model=model,
                            task_group=None,
                            function=cls.FUNCTION,
                            api_key=api_key,
                            input=input,
                            is_service=False,
                            workspace=workspace,
                            **parameters)

    @classmethod
    def _build_llm_parameters(cls, model, prompt, history, messages, **kwargs):
        parameters = {}
        input = {}
        if history is not None:
            logger.warning(DEPRECATED_MESSAGE)
            input[HISTORY] = history
            if prompt is not None and prompt:
                input[PROMPT] = prompt
        elif messages is not None:
            msgs = copy.deepcopy(messages)
            if prompt is not None and prompt:
                msgs.append({'role': Role.USER, 'content': prompt})
            input = {MESSAGES: msgs}
        else:
            input[PROMPT] = prompt

        if model.startswith('qwen'):
            enable_search = kwargs.pop('enable_search', False)
            if enable_search:
                parameters['enable_search'] = enable_search
        elif model.startswith('bailian'):
            customized_model_id = kwargs.pop('customized_model_id', None)
            if customized_model_id is None:
                raise InputRequired('customized_model_id is required for %s' %
                                    model)
            input[CUSTOMIZED_MODEL_ID] = customized_model_id

        return input, {**parameters, **kwargs}
