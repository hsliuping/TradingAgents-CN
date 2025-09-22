# Copyright (c) Alibaba, Inc. and its affiliates.

import copy
import json
from typing import Any, Dict, Generator, List, Union

from dashscope.api_entities.dashscope_response import (GenerationResponse,
                                                       Message, Role)
from dashscope.client.base_api import BaseAioApi, BaseApi
from dashscope.common.constants import (CUSTOMIZED_MODEL_ID,
                                        DEPRECATED_MESSAGE, HISTORY, MESSAGES,
                                        PROMPT)
from dashscope.common.error import InputRequired, ModelRequired
from dashscope.common.logging import logger
from dashscope.common.utils import _get_task_group_and_task


class Generation(BaseApi):
    task = 'text-generation'
    """API for AI-Generated Content(AIGC) models.

    """
    class Models:
        """@deprecated, use qwen_turbo instead"""
        qwen_v1 = 'qwen-v1'
        """@deprecated, use qwen_plus instead"""
        qwen_plus_v1 = 'qwen-plus-v1'

        bailian_v1 = 'bailian-v1'
        dolly_12b_v2 = 'dolly-12b-v2'
        qwen_turbo = 'qwen-turbo'
        qwen_plus = 'qwen-plus'
        qwen_max = 'qwen-max'

    @classmethod
    def call(
        cls,
        model: str,
        prompt: Any = None,
        history: list = None,
        api_key: str = None,
        messages: List[Message] = None,
        plugins: Union[str, Dict[str, Any]] = None,
        workspace: str = None,
        **kwargs
    ) -> Union[GenerationResponse, Generator[GenerationResponse, None, None]]:
        """Call generation model service.

        Args:
            model (str): The requested model, such as qwen-turbo
            prompt (Any): The input prompt.
            history (list):The user provided history, deprecated
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
            plugins (Any): The plugin config. Can be plugins config str, or dict.
            **kwargs:
                stream(bool, `optional`): Enable server-sent events
                    (ref: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)  # noqa E501
                    the result will back partially[qwen-turbo,bailian-v1].
                temperature(float, `optional`): Used to control the degree
                    of randomness and diversity. Specifically, the temperature
                    value controls the degree to which the probability distribution
                    of each candidate word is smoothed when generating text.
                    A higher temperature value will reduce the peak value of
                    the probability, allowing more low-probability words to be
                    selected, and the generated results will be more diverse;
                    while a lower temperature value will enhance the peak value
                    of the probability, making it easier for high-probability
                    words to be selected, the generated results are more
                    deterministic, range(0, 2) .[qwen-turbo,qwen-plus].
                top_p(float, `optional`): A sampling strategy, called nucleus
                    sampling, where the model considers the results of the
                    tokens with top_p probability mass. So 0.1 means only
                    the tokens comprising the top 10% probability mass are
                    considered[qwen-turbo,bailian-v1].
                top_k(int, `optional`): The size of the sample candidate set when generated.  # noqa E501
                    For example, when the value is 50, only the 50 highest-scoring tokens  # noqa E501
                    in a single generation form a randomly sampled candidate set. # noqa E501
                    The larger the value, the higher the randomness generated;  # noqa E501
                    the smaller the value, the higher the certainty generated. # noqa E501
                    The default value is 0, which means the top_k policy is  # noqa E501
                    not enabled. At this time, only the top_p policy takes effect. # noqa E501
                enable_search(bool, `optional`): Whether to enable web search(quark).  # noqa E501
                    Currently works best only on the first round of conversation.
                    Default to False, support model: [qwen-turbo].
                customized_model_id(str, required) The enterprise-specific
                    large model id, which needs to be generated from the
                    operation background of the enterprise-specific
                    large model product, support model: [bailian-v1].
                result_format(str, `optional`): [message|text] Set result result format. # noqa E501
                    Default result is text
                incremental_output(bool, `optional`): Used to control the streaming output mode. # noqa E501
                    If true, the subsequent output will include the previously input content. # noqa E501
                    Otherwise, the subsequent output will not include the previously output # noqa E501
                    content. Default false.
                stop(list[str] or list[list[int]], `optional`): Used to control the generation to stop  # noqa E501
                    when encountering setting str or token ids, the result will not include # noqa E501
                    stop words or tokens.
                max_tokens(int, `optional`): The maximum token num expected to be output. It should be # noqa E501
                    noted that the length generated by the model will only be less than max_tokens,  # noqa E501
                    not necessarily equal to it. If max_tokens is set too large, the service will # noqa E501
                    directly prompt that the length exceeds the limit. It is generally # noqa E501
                    not recommended to set this value.
                repetition_penalty(float, `optional`): Used to control the repeatability when generating models.  # noqa E501
                    Increasing repetition_penalty can reduce the duplication of model generation.  # noqa E501
                    1.0 means no punishment.
            workspace (str): The dashscope workspace id.
        Raises:
            InvalidInput: The history and auto_history are mutually exclusive.

        Returns:
            Union[GenerationResponse,
                  Generator[GenerationResponse, None, None]]: If
            stream is True, return Generator, otherwise GenerationResponse.
        """
        if (prompt is None or not prompt) and (messages is None
                                               or not messages):
            raise InputRequired('prompt or messages is required!')
        if model is None or not model:
            raise ModelRequired('Model is required!')
        task_group, function = _get_task_group_and_task(__name__)
        if plugins is not None:
            headers = kwargs.pop('headers', {})
            if isinstance(plugins, str):
                headers['X-DashScope-Plugin'] = plugins
            else:
                headers['X-DashScope-Plugin'] = json.dumps(plugins)
            kwargs['headers'] = headers
        input, parameters = cls._build_input_parameters(
            model, prompt, history, messages, **kwargs)
        response = super().call(model=model,
                                task_group=task_group,
                                task=Generation.task,
                                function=function,
                                api_key=api_key,
                                input=input,
                                workspace=workspace,
                                **parameters)
        is_stream = kwargs.get('stream', False)
        if is_stream:
            return (GenerationResponse.from_api_response(rsp)
                    for rsp in response)
        else:
            return GenerationResponse.from_api_response(response)

    @classmethod
    def _build_input_parameters(cls, model, prompt, history, messages,
                                **kwargs):
        if model == Generation.Models.qwen_v1:
            logger.warning(
                'Model %s is deprecated, use %s instead!' %
                (Generation.Models.qwen_v1, Generation.Models.qwen_turbo))
        if model == Generation.Models.qwen_plus_v1:
            logger.warning(
                'Model %s is deprecated, use %s instead!' %
                (Generation.Models.qwen_plus_v1, Generation.Models.qwen_plus))
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


class AioGeneration(BaseAioApi):
    task = 'text-generation'
    """API for AI-Generated Content(AIGC) models.

    """
    class Models:
        """@deprecated, use qwen_turbo instead"""
        qwen_v1 = 'qwen-v1'
        """@deprecated, use qwen_plus instead"""
        qwen_plus_v1 = 'qwen-plus-v1'

        bailian_v1 = 'bailian-v1'
        dolly_12b_v2 = 'dolly-12b-v2'
        qwen_turbo = 'qwen-turbo'
        qwen_plus = 'qwen-plus'
        qwen_max = 'qwen-max'

    @classmethod
    async def call(
        cls,
        model: str,
        prompt: Any = None,
        history: list = None,
        api_key: str = None,
        messages: List[Message] = None,
        plugins: Union[str, Dict[str, Any]] = None,
        workspace: str = None,
        **kwargs
    ) -> Union[GenerationResponse, Generator[GenerationResponse, None, None]]:
        """Call generation model service.

        Args:
            model (str): The requested model, such as qwen-turbo
            prompt (Any): The input prompt.
            history (list):The user provided history, deprecated
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
            plugins (Any): The plugin config. Can be plugins config str, or dict.
            **kwargs:
                stream(bool, `optional`): Enable server-sent events
                    (ref: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)  # noqa E501
                    the result will back partially[qwen-turbo,bailian-v1].
                temperature(float, `optional`): Used to control the degree
                    of randomness and diversity. Specifically, the temperature
                    value controls the degree to which the probability distribution
                    of each candidate word is smoothed when generating text.
                    A higher temperature value will reduce the peak value of
                    the probability, allowing more low-probability words to be
                    selected, and the generated results will be more diverse;
                    while a lower temperature value will enhance the peak value
                    of the probability, making it easier for high-probability
                    words to be selected, the generated results are more
                    deterministic, range(0, 2) .[qwen-turbo,qwen-plus].
                top_p(float, `optional`): A sampling strategy, called nucleus
                    sampling, where the model considers the results of the
                    tokens with top_p probability mass. So 0.1 means only
                    the tokens comprising the top 10% probability mass are
                    considered[qwen-turbo,bailian-v1].
                top_k(int, `optional`): The size of the sample candidate set when generated.  # noqa E501
                    For example, when the value is 50, only the 50 highest-scoring tokens  # noqa E501
                    in a single generation form a randomly sampled candidate set. # noqa E501
                    The larger the value, the higher the randomness generated;  # noqa E501
                    the smaller the value, the higher the certainty generated. # noqa E501
                    The default value is 0, which means the top_k policy is  # noqa E501
                    not enabled. At this time, only the top_p policy takes effect. # noqa E501
                enable_search(bool, `optional`): Whether to enable web search(quark).  # noqa E501
                    Currently works best only on the first round of conversation.
                    Default to False, support model: [qwen-turbo].
                customized_model_id(str, required) The enterprise-specific
                    large model id, which needs to be generated from the
                    operation background of the enterprise-specific
                    large model product, support model: [bailian-v1].
                result_format(str, `optional`): [message|text] Set result result format. # noqa E501
                    Default result is text
                incremental_output(bool, `optional`): Used to control the streaming output mode. # noqa E501
                    If true, the subsequent output will include the previously input content. # noqa E501
                    Otherwise, the subsequent output will not include the previously output # noqa E501
                    content. Default false.
                stop(list[str] or list[list[int]], `optional`): Used to control the generation to stop  # noqa E501
                    when encountering setting str or token ids, the result will not include # noqa E501
                    stop words or tokens.
                max_tokens(int, `optional`): The maximum token num expected to be output. It should be # noqa E501
                    noted that the length generated by the model will only be less than max_tokens,  # noqa E501
                    not necessarily equal to it. If max_tokens is set too large, the service will # noqa E501
                    directly prompt that the length exceeds the limit. It is generally # noqa E501
                    not recommended to set this value.
                repetition_penalty(float, `optional`): Used to control the repeatability when generating models.  # noqa E501
                    Increasing repetition_penalty can reduce the duplication of model generation.  # noqa E501
                    1.0 means no punishment.
            workspace (str): The dashscope workspace id.
        Raises:
            InvalidInput: The history and auto_history are mutually exclusive.

        Returns:
            Union[GenerationResponse,
                  Generator[GenerationResponse, None, None]]: If
            stream is True, return Generator, otherwise GenerationResponse.
        """
        if (prompt is None or not prompt) and (messages is None
                                               or not messages):
            raise InputRequired('prompt or messages is required!')
        if model is None or not model:
            raise ModelRequired('Model is required!')
        task_group, function = _get_task_group_and_task(__name__)
        if plugins is not None:
            headers = kwargs.pop('headers', {})
            if isinstance(plugins, str):
                headers['X-DashScope-Plugin'] = plugins
            else:
                headers['X-DashScope-Plugin'] = json.dumps(plugins)
            kwargs['headers'] = headers
        input, parameters = Generation._build_input_parameters(
            model, prompt, history, messages, **kwargs)
        response = await super().call(model=model,
                                      task_group=task_group,
                                      task=Generation.task,
                                      function=function,
                                      api_key=api_key,
                                      input=input,
                                      workspace=workspace,
                                      **parameters)
        is_stream = kwargs.get('stream', False)
        if is_stream:
            return (GenerationResponse.from_api_response(rsp)
                    async for rsp in response)
        else:
            return GenerationResponse.from_api_response(response)
