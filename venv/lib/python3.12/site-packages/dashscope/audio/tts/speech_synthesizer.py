# Copyright (c) Alibaba, Inc. and its affiliates.

from http import HTTPStatus
from typing import Dict, List

from dashscope.api_entities.dashscope_response import SpeechSynthesisResponse
from dashscope.client.base_api import BaseApi
from dashscope.common.constants import ApiProtocol
from dashscope.common.utils import _get_task_group_and_task


class SpeechSynthesisResult():
    """The result set of speech synthesis, including audio data,
       timestamp information, and final result information.
    """

    _audio_frame: bytes = None
    _audio_data: bytes = None
    _sentence: Dict[str, str] = None
    _sentences: List[Dict[str, str]] = None
    _response: SpeechSynthesisResponse = None

    def __init__(self, frame: bytes, data: bytes, sentence: Dict[str, str],
                 sentences: List[Dict[str, str]],
                 response: SpeechSynthesisResponse):
        if frame is not None:
            self._audio_frame = bytes(frame)
        if data is not None:
            self._audio_data = bytes(data)
        if sentence is not None:
            self._sentence = sentence
        if sentences is not None:
            self._sentences = sentences
        if response is not None:
            self._response = response

    def get_audio_frame(self) -> bytes:
        """Obtain the audio frame data of speech synthesis through callbacks.
        """
        return self._audio_frame

    def get_audio_data(self) -> bytes:
        """Get complete audio data for speech synthesis.
        """
        return self._audio_data

    def get_timestamp(self) -> Dict[str, str]:
        """Obtain the timestamp information of the current speech synthesis
        sentence through the callback.
        """
        return self._sentence

    def get_timestamps(self) -> List[Dict[str, str]]:
        """Get complete timestamp information for all speech synthesis sentences.
        """
        return self._sentences

    def get_response(self) -> SpeechSynthesisResponse:
        """Obtain the status information of the current speech synthesis task,
        including error information and billing information.
        """
        return self._response


class ResultCallback():
    """
    An interface that defines callback methods for getting speech synthesis results. # noqa E501
    Derive from this class and implement its function to provide your own data.
    """
    def on_open(self) -> None:
        pass

    def on_complete(self) -> None:
        pass

    def on_error(self, response: SpeechSynthesisResponse) -> None:
        pass

    def on_close(self) -> None:
        pass

    def on_event(self, result: SpeechSynthesisResult) -> None:
        pass


class SpeechSynthesizer(BaseApi):
    """Text-to-speech interface.
    """
    class AudioFormat:
        format_wav = 'wav'
        format_pcm = 'pcm'
        format_mp3 = 'mp3'

    @classmethod
    def call(cls,
             model: str,
             text: str,
             callback: ResultCallback = None,
             workspace: str = None,
             **kwargs) -> SpeechSynthesisResult:
        """Convert text to speech synchronously.

        Args:
            model (str): The requested model_id.
            text (str): Text content used for speech synthesis.
            callback (ResultCallback): A callback that returns
                speech synthesis results.
            workspace (str): The dashscope workspace id.
            **kwargs:
                format(str, `optional`): Audio encoding format,
                    such as pcm wav mp3, default is wav.
                sample_rate(int, `optional`): Audio sample rate,
                    default is the sample rate of model.
                volume(int, `optional`): The volume of synthesized speech
                    ranges from 0~100, default is 50.
                rate(float, `optional`): The speech rate of synthesized
                    speech, the value range is 0.5~2.0, default is 1.0.
                pitch(float, `optional`): The intonation of synthesized
                    speech,the value range is 0.5~2.0, default is 1.0.
                word_timestamp_enabled(bool, `optional`): Turn on word-level
                    timestamping, default is False.
                phoneme_timestamp_enabled(bool, `optional`): Turn on phoneme
                    level timestamping, default is False.

        Returns:
            SpeechSynthesisResult: The result of systhesis.
        """
        _callback = callback
        _audio_data: bytes = None
        _sentences: List[Dict[str, str]] = []
        _the_final_response = None
        _task_failed_flag: bool = False
        task_name, _ = _get_task_group_and_task(__name__)

        response = super().call(model=model,
                                task_group='audio',
                                task=task_name,
                                function='SpeechSynthesizer',
                                input={'text': text},
                                stream=True,
                                api_protocol=ApiProtocol.WEBSOCKET,
                                workspace=workspace,
                                **kwargs)

        if _callback is not None:
            _callback.on_open()

        for part in response:
            if isinstance(part.output, bytes):
                if _callback is not None:
                    audio_frame = SpeechSynthesisResult(
                        bytes(part.output), None, None, None, None)
                    _callback.on_event(audio_frame)

                if _audio_data is None:
                    _audio_data = bytes(part.output)
                else:
                    _audio_data = _audio_data + bytes(part.output)

            else:
                if part.status_code == HTTPStatus.OK:
                    if part.output is None:
                        _the_final_response = SpeechSynthesisResponse.from_api_response(  # noqa E501
                            part)
                    else:
                        if _callback is not None:
                            sentence = SpeechSynthesisResult(
                                None, None, part.output['sentence'], None,
                                None)
                            _callback.on_event(sentence)
                        if len(_sentences) == 0:
                            _sentences.append(part.output['sentence'])
                        else:
                            if _sentences[-1]['begin_time'] == part.output[
                                    'sentence']['begin_time']:
                                if _sentences[-1]['end_time'] != part.output[
                                        'sentence']['end_time']:
                                    _sentences.pop()
                                    _sentences.append(part.output['sentence'])
                            else:
                                _sentences.append(part.output['sentence'])
                else:
                    _task_failed_flag = True
                    _the_final_response = SpeechSynthesisResponse.from_api_response(  # noqa E501
                        part)
                    if _callback is not None:
                        _callback.on_error(
                            SpeechSynthesisResponse.from_api_response(part))

        if _callback is not None:
            if _task_failed_flag is False:
                _callback.on_complete()
            _callback.on_close()

        result = SpeechSynthesisResult(None, _audio_data, None, _sentences,
                                       _the_final_response)
        return result
