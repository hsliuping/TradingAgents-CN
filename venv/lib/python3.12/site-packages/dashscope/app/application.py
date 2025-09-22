# Copyright (c) Alibaba, Inc. and its affiliates.
"""
@File    :   application.py
@Date    :   2024-02-24
@Desc    :   Application calls for both http and http sse
"""
import copy
from typing import Generator, List, Union

from dashscope.api_entities.api_request_factory import _build_api_request
from dashscope.api_entities.dashscope_response import Message, Role
from dashscope.app.application_response import ApplicationResponse
from dashscope.client.base_api import BaseApi
from dashscope.common.api_key import get_default_api_key
from dashscope.common.constants import (DEPRECATED_MESSAGE, HISTORY, MESSAGES,
                                        PROMPT)
from dashscope.common.error import InputRequired, InvalidInput
from dashscope.common.logging import logger


class Application(BaseApi):
    task_group = 'apps'
    function = 'completion'
    """API for app completion calls.

    """
    class DocReferenceType:
        """ doc reference type for rag completion """

        simple = 'simple'

        indexed = 'indexed'

    @classmethod
    def _validate_params(cls, api_key, app_id):
        if api_key is None:
            api_key = get_default_api_key()

        if app_id is None or not app_id:
            raise InputRequired('App id is required!')

        return api_key, app_id

    @classmethod
    def call(
        cls,
        app_id: str,
        prompt: str = None,
        history: list = None,
        workspace: str = None,
        api_key: str = None,
        messages: List[Message] = None,
        **kwargs
    ) -> Union[ApplicationResponse, Generator[ApplicationResponse, None,
                                              None]]:
        """Call app completion service.

        Args:
            app_id (str): Id of bailian application
            prompt (str): The input prompt.
            history (list):The user provided history
                examples:
                    [{'user':'The weather is fine today.',
                    'bot': 'Suitable for outings'}].
                Defaults to None.
            workspace(str, `optional`): Workspace for app completion call
            api_key (str, optional): The api api_key, can be None,
                if None, will get by default rule(TODO: api key doc).
            messages(list): The generation messages.

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
                seed(int, `optional`): When generating, the seed of the random number is used to control the
                    randomness of the model generation. If you use the same seed, each run will generate the same results;
                    you can use the same seed when you need to reproduce the model's generated results.
                    The seed parameter supports unsigned 64-bit integer types. Default value 1234
                session_id(str, `optional`): Session if for multiple rounds call.
                biz_params(dict, `optional`): The extra parameters for flow or plugin.
                has_thoughts(bool, `optional`): Flag to return rag or plugin process details. Default value false.
                doc_tag_codes(list[str], `optional`): Tag code list for doc retrival.
                doc_reference_type(str, `optional`): The type of doc reference.
                    simple: simple format of doc retrival which not include index in response text but in doc reference list.
                    indexed: include both index in response text and doc reference list
                memory_id(str, `optional`): Used to store long term context summary between end users and assistant.
                image_list(list, `optional`): Used to pass image url list.
                rag_options(dict, `optional`): Rag options for retrieval augmented generation options.
        Raises:
            InvalidInput: The history and auto_history are mutually exclusive.

        Returns:
            Union[CompletionResponse,
                  Generator[CompletionResponse, None, None]]: If
            stream is True, return Generator, otherwise GenerationResponse.
        """

        api_key, app_id = Application._validate_params(api_key, app_id)

        if (prompt is None or not prompt) and (messages is None
                                               or len(messages) == 0):
            raise InputRequired('prompt or messages is required!')

        if workspace is not None and workspace:
            headers = kwargs.pop('headers', {})
            headers['X-DashScope-WorkSpace'] = workspace
            kwargs['headers'] = headers

        input, parameters = cls._build_input_parameters(
            prompt, history, messages, **kwargs)
        request = _build_api_request(model='',
                                     input=input,
                                     task_group=Application.task_group,
                                     task=app_id,
                                     function=Application.function,
                                     workspace=workspace,
                                     api_key=api_key,
                                     is_service=False,
                                     **parameters)
        # call request service.
        response = request.call()
        is_stream = kwargs.get('stream', False)

        if is_stream:
            return (ApplicationResponse.from_api_response(rsp)
                    for rsp in response)
        else:
            return ApplicationResponse.from_api_response(response)

    @classmethod
    def _build_input_parameters(cls, prompt, history, messages, **kwargs):
        parameters = {}

        input_param = {}
        if messages is not None:
            msgs = copy.deepcopy(messages)
            if prompt is not None and prompt:
                msgs.append({'role': Role.USER, 'content': prompt})
            input_param = {MESSAGES: msgs}
        elif history is not None and history:
            logger.warning(DEPRECATED_MESSAGE)
            input_param[HISTORY] = history
            if prompt is not None and prompt:
                input_param[PROMPT] = prompt
        else:
            input_param[PROMPT] = prompt

        session_id = kwargs.pop('session_id', None)
        if session_id is not None and session_id:
            input_param['session_id'] = session_id

        doc_reference_type = kwargs.pop('doc_reference_type', None)
        if doc_reference_type is not None and doc_reference_type:
            input_param['doc_reference_type'] = doc_reference_type

        doc_tag_codes = kwargs.pop('doc_tag_codes', None)
        if doc_tag_codes is not None:
            if isinstance(doc_tag_codes, list) and all(
                    isinstance(item, str) for item in doc_tag_codes):
                input_param['doc_tag_codes'] = doc_tag_codes
            else:
                raise InvalidInput('doc_tag_codes is not a List[str]')

        memory_id = kwargs.pop('memory_id', None)
        if memory_id is not None:
            input_param['memory_id'] = memory_id

        biz_params = kwargs.pop('biz_params', None)
        if biz_params is not None and biz_params:
            input_param['biz_params'] = biz_params

        image_list = kwargs.pop('image_list', None)
        if image_list is not None and image_list:
            input_param['image_list'] = image_list

        return input_param, {**parameters, **kwargs}
