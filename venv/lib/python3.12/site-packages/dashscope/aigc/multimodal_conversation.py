# Copyright (c) Alibaba, Inc. and its affiliates.

import copy
from typing import Generator, List, Union

from dashscope.api_entities.dashscope_response import \
    MultiModalConversationResponse
from dashscope.client.base_api import BaseApi
from dashscope.common.error import InputRequired, ModelRequired
from dashscope.common.utils import _get_task_group_and_task
from dashscope.utils.oss_utils import preprocess_message_element


class MultiModalConversation(BaseApi):
    """MultiModal conversational robot interface.
    """
    task = 'multimodal-generation'
    function = 'generation'

    class Models:
        qwen_vl_chat_v1 = 'qwen-vl-chat-v1'

    @classmethod
    def call(
        cls,
        model: str,
        messages: List,
        api_key: str = None,
        workspace: str = None,
        **kwargs
    ) -> Union[MultiModalConversationResponse, Generator[
            MultiModalConversationResponse, None, None]]:
        """Call the conversation model service.

        Args:
            model (str): The requested model, such as 'qwen-multimodal-v1'
            messages (list): The generation messages.
                examples:
                    [
                        {
                            "role": "system",
                            "content": [
                                {"text": "你是达摩院的生活助手机器人。"}
                            ]
                        },
                        {
                            "role": "user",
                            "content": [
                                {"image": "http://XXXX"},
                                {"text": "这个图片是哪里？"},
                            ]
                        }
                    ]
            api_key (str, optional): The api api_key, can be None,
                if None, will retrieve by rule [1].
                [1]: https://help.aliyun.com/zh/dashscope/developer-reference/api-key-settings. # noqa E501
            workspace (str): The dashscope workspace id.
            **kwargs:
                stream(bool, `optional`): Enable server-sent events
                    (ref: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)  # noqa E501
                    the result will back partially[qwen-turbo,bailian-v1].
                max_length(int, `optional`): The maximum length of tokens to
                    generate. The token count of your prompt plus max_length
                    cannot exceed the model's context length. Most models
                    have a context length of 2000 tokens[qwen-turbo,bailian-v1]. # noqa E501
                top_p(float, `optional`): A sampling strategy, called nucleus
                    sampling, where the model considers the results of the
                    tokens with top_p probability mass. So 0.1 means only
                    the tokens comprising the top 10% probability mass are
                    considered[qwen-turbo,bailian-v1].
                top_k(float, `optional`):

        Raises:
            InvalidInput: The history and auto_history are mutually exclusive.

        Returns:
            Union[MultiModalConversationResponse,
                  Generator[MultiModalConversationResponse, None, None]]: If
            stream is True, return Generator, otherwise MultiModalConversationResponse.
        """
        if (messages is None or not messages):
            raise InputRequired('prompt or messages is required!')
        if model is None or not model:
            raise ModelRequired('Model is required!')
        task_group, _ = _get_task_group_and_task(__name__)
        msg_copy = copy.deepcopy(messages)
        has_upload = cls._preprocess_messages(model, msg_copy, api_key)
        if has_upload:
            headers = kwargs.pop('headers', {})
            headers['X-DashScope-OssResourceResolve'] = 'enable'
            kwargs['headers'] = headers
        input = {'messages': msg_copy}
        response = super().call(model=model,
                                task_group=task_group,
                                task=MultiModalConversation.task,
                                function=MultiModalConversation.function,
                                api_key=api_key,
                                input=input,
                                workspace=workspace,
                                **kwargs)
        is_stream = kwargs.get('stream', False)
        if is_stream:
            return (MultiModalConversationResponse.from_api_response(rsp)
                    for rsp in response)
        else:
            return MultiModalConversationResponse.from_api_response(response)

    @classmethod
    def _preprocess_messages(cls, model: str, messages: List[dict],
                             api_key: str):
        """
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"image": ""},
                        {"text": ""},
                    ]
                }
            ]
        """
        has_upload = False
        for message in messages:
            content = message['content']
            for elem in content:
                if not isinstance(elem,
                                  (int, float, bool, str, bytes, bytearray)):
                    is_upload = preprocess_message_element(
                        model, elem, api_key)
                    if is_upload and not has_upload:
                        has_upload = True
        return has_upload
