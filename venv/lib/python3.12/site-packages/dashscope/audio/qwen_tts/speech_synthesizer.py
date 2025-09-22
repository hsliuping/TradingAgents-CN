# Copyright (c) Alibaba, Inc. and its affiliates.

from typing import Generator, Union

from dashscope.api_entities.dashscope_response import \
    TextToSpeechResponse
from dashscope.client.base_api import BaseApi
from dashscope.common.error import InputRequired, ModelRequired


class SpeechSynthesizer(BaseApi):
    """Text-to-speech interface.
    """

    task_group = 'aigc'
    task = 'multimodal-generation'
    function = 'generation'

    class Models:
        qwen_tts = 'qwen-tts'

    @classmethod
    def call(
        cls,
        model: str,
        text: str,
        api_key: str = None,
        workspace: str = None,
        **kwargs
    ) -> Union[TextToSpeechResponse, Generator[
            TextToSpeechResponse, None, None]]:
        """Call the conversation model service.

        Args:
            model (str): The requested model, such as 'qwen-tts'
            text (str): Text content used for speech synthesis.
            api_key (str, optional): The api api_key, can be None,
                if None, will retrieve by rule [1].
                [1]: https://help.aliyun.com/zh/dashscope/developer-reference/api-key-settings. # noqa E501
            workspace (str): The dashscope workspace id.
            **kwargs:
                stream(bool, `optional`): Enable server-sent events
                    (ref: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)  # noqa E501
                    the result will back partially[qwen-turbo,bailian-v1].
                voice: str
                    Voice name.

        Raises:
            InputRequired: The input must include the text parameter.
            ModelRequired: The input must include the model parameter.

        Returns:
            Union[TextToSpeechResponse,
                  Generator[TextToSpeechResponse, None, None]]: If
            stream is True, return Generator, otherwise TextToSpeechResponse.
        """
        if not text:
            raise InputRequired('text is required!')
        if model is None or not model:
            raise ModelRequired('Model is required!')
        input = {'text': text}
        if 'voice' in kwargs:
            input['voice'] = kwargs.pop('voice')
        response = super().call(model=model,
                                task_group=SpeechSynthesizer.task_group,
                                task=SpeechSynthesizer.task,
                                function=SpeechSynthesizer.function,
                                api_key=api_key,
                                input=input,
                                workspace=workspace,
                                **kwargs)
        is_stream = kwargs.get('stream', False)
        if is_stream:
            return (TextToSpeechResponse.from_api_response(rsp)
                    for rsp in response)
        else:
            return TextToSpeechResponse.from_api_response(response)
