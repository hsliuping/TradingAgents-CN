# Copyright (c) Alibaba, Inc. and its affiliates.

import json
import os
import threading
import time
import uuid
from http import HTTPStatus
from queue import Queue
from threading import Timer
from typing import Any, Dict, List, Union

from dashscope.api_entities.dashscope_response import RecognitionResponse
from dashscope.client.base_api import BaseApi
from dashscope.common.constants import ApiProtocol
from dashscope.common.error import (InputDataRequired, InputRequired,
                                    InvalidParameter, InvalidTask,
                                    ModelRequired)
from dashscope.common.logging import logger
from dashscope.common.utils import _get_task_group_and_task
from dashscope.protocol.websocket import WebsocketStreamingMode


class RecognitionResult(RecognitionResponse):
    """The result set of speech recognition, including the single-sentence
       recognition result returned by the callback mode, and all recognition
       results in a synchronized manner.
    """
    def __init__(self,
                 response: RecognitionResponse,
                 sentences: List[Any] = None,
                 usages: List[Any] = None):
        self.status_code = response.status_code
        self.request_id = response.request_id
        self.code = response.code
        self.message = response.message
        self.usages = usages
        if sentences is not None and len(sentences) > 0:
            self.output = {'sentence': sentences}
        else:
            self.output = response.output
        if self.usages is not None and len(
                self.usages) > 0 and 'usage' in self.usages[-1]:
            self.usage = self.usages[-1]['usage']
        else:
            self.usage = None

    def __str__(self):
        return json.dumps(RecognitionResponse.from_api_response(self),
                          ensure_ascii=False)

    def get_sentence(self) -> Union[Dict[str, Any], List[Any]]:
        """The result of speech recognition.
        """
        if self.output and 'sentence' in self.output:
            return self.output['sentence']
        else:
            return None

    def get_request_id(self) -> str:
        """The request_id of speech recognition.
        """
        return self.request_id

    def get_usage(self, sentence: Dict[str, Any]) -> Dict[str, Any]:
        """Get billing for the input sentence.
        """
        if self.usages is not None:
            if sentence is not None and 'end_time' in sentence and sentence[
                    'end_time'] is not None:
                for usage in self.usages:
                    if usage['end_time'] == sentence['end_time']:
                        return usage['usage']

        return None

    @staticmethod
    def is_sentence_end(sentence: Dict[str, Any]) -> bool:
        """Determine whether the speech recognition result is the end of a sentence.
           This is a static method.
        """
        if sentence is not None and 'end_time' in sentence and sentence[
                'end_time'] is not None:
            return True
        else:
            return False


class RecognitionCallback():
    """An interface that defines callback methods for getting speech recognition results. # noqa E501
       Derive from this class and implement its function to provide your own data.
    """
    def on_open(self) -> None:
        pass

    def on_complete(self) -> None:
        pass

    def on_error(self, result: RecognitionResult) -> None:
        pass

    def on_close(self) -> None:
        pass

    def on_event(self, result: RecognitionResult) -> None:
        pass


class Recognition(BaseApi):
    """Speech recognition interface.

    Args:
        model (str): The requested model_id.
        callback (RecognitionCallback): A callback that returns
            speech recognition results.
        format (str): The input audio format for speech recognition.
        sample_rate (int): The input audio sample rate for speech recognition.
        workspace (str): The dashscope workspace id.

        **kwargs:
            phrase_id (list, `optional`): The ID of phrase.
            disfluency_removal_enabled(bool, `optional`): Filter mood words,
                turned off by default.
            diarization_enabled (bool, `optional`): Speech auto diarization,
                turned off by default.
            speaker_count (int, `optional`): The number of speakers.
            timestamp_alignment_enabled (bool, `optional`): Timestamp-alignment
                calibration, turned off by default.
            special_word_filter(str, `optional`): Sensitive word filter.
            audio_event_detection_enabled(bool, `optional`):
                Audio event detection, turned off by default.

    Raises:
        InputRequired: Input is required.
    """

    SILENCE_TIMEOUT_S = 23

    def __init__(self,
                 model: str,
                 callback: RecognitionCallback,
                 format: str,
                 sample_rate: int,
                 workspace: str = None,
                 **kwargs):
        if model is None:
            raise ModelRequired('Model is required!')
        if format is None:
            raise InputRequired('format is required!')
        if sample_rate is None:
            raise InputRequired('sample_rate is required!')

        self.model = model
        self.format = format
        self.sample_rate = sample_rate
        # continuous recognition with start() or once recognition with call()
        self._recognition_once = False
        self._callback = callback
        self._running = False
        self._stream_data = Queue()
        self._worker = None
        self._silence_timer = None
        self._kwargs = kwargs
        self._workspace = workspace
        self._start_stream_timestamp = -1
        self._first_package_timestamp = -1
        self._stop_stream_timestamp = -1
        self._on_complete_timestamp = -1
        self.request_id_confirmed = False
        self.last_request_id = uuid.uuid4().hex

    def __del__(self):
        if self._running:
            self._running = False
            self._stream_data = Queue()
            if self._worker is not None and self._worker.is_alive():
                self._worker.join()
            if self._silence_timer is not None and self._silence_timer.is_alive(  # noqa E501
            ):
                self._silence_timer.cancel()
                self._silence_timer = None
            if self._callback:
                self._callback.on_close()

    def __receive_worker(self):
        """Asynchronously, initiate a real-time speech recognition request and
           obtain the result for parsing.
        """
        responses = self.__launch_request()
        for part in responses:
            if part.status_code == HTTPStatus.OK:
                if len(part.output) == 0:
                    self._on_complete_timestamp = time.time() * 1000
                    logger.debug('last package delay {}'.format(
                        self.get_last_package_delay()))
                    self._callback.on_complete()
                else:
                    usage: Dict[str, Any] = None
                    usages: List[Any] = None
                    if 'sentence' in part.output:
                        if (self._first_package_timestamp < 0):
                            self._first_package_timestamp = time.time() * 1000
                            logger.debug('first package delay {}'.format(
                                self.get_first_package_delay()))
                        sentence = part.output['sentence']
                        if 'heartbeat' in sentence and sentence['heartbeat'] == True:
                            logger.debug('recv heartbeat')
                            continue
                        logger.debug(
                            'Recv Result [rid:{}]:{}, isEnd: {}'.format(
                                part.request_id, sentence,
                                RecognitionResult.is_sentence_end(sentence)))
                        if part.usage is not None:
                            usage = {
                                'end_time':
                                part.output['sentence']['end_time'],
                                'usage': part.usage
                            }
                            usages = [usage]
                        if self.request_id_confirmed is False and part.request_id is not None:
                            self.last_request_id = part.request_id
                            self.request_id_confirmed = True

                    self._callback.on_event(
                        RecognitionResult(
                            RecognitionResponse.from_api_response(part),
                            usages=usages))
            else:
                self._running = False
                self._stream_data = Queue()
                self._callback.on_error(
                    RecognitionResult(
                        RecognitionResponse.from_api_response(part)))
                self._callback.on_close()
                break

    def __launch_request(self):
        """Initiate real-time speech recognition requests.
        """
        resources_list: list = []
        if self._phrase is not None and len(self._phrase) > 0:
            item = {'resource_id': self._phrase, 'resource_type': 'asr_phrase'}
            resources_list.append(item)

            if len(resources_list) > 0:
                self._kwargs['resources'] = resources_list

        self._tidy_kwargs()
        task_name, _ = _get_task_group_and_task(__name__)
        responses = super().call(model=self.model,
                                 task_group='audio',
                                 task=task_name,
                                 function='recognition',
                                 input=self._input_stream_cycle(),
                                 api_protocol=ApiProtocol.WEBSOCKET,
                                 ws_stream_mode=WebsocketStreamingMode.DUPLEX,
                                 is_binary_input=True,
                                 sample_rate=self.sample_rate,
                                 format=self.format,
                                 stream=True,
                                 workspace=self._workspace,
                                 pre_task_id=self.last_request_id,
                                 **self._kwargs)
        return responses

    def start(self, phrase_id: str = None, **kwargs):
        """Real-time speech recognition in asynchronous mode.
           Please call 'stop()' after you have completed recognition.

        Args:
            phrase_id (str, `optional`): The ID of phrase.

            **kwargs:
                disfluency_removal_enabled(bool, `optional`):
                    Filter mood words, turned off by default.
                diarization_enabled (bool, `optional`):
                    Speech auto diarization, turned off by default.
                speaker_count (int, `optional`): The number of speakers.
                timestamp_alignment_enabled (bool, `optional`):
                    Timestamp-alignment calibration, turned off by default.
                special_word_filter(str, `optional`): Sensitive word filter.
                audio_event_detection_enabled(bool, `optional`):
                    Audio event detection, turned off by default.

        Raises:
            InvalidParameter: This interface cannot be called again
                if it has already been started.
            InvalidTask: Task create failed.
        """
        assert self._callback is not None, 'Please set the callback to get the speech recognition result.'  # noqa E501

        if self._running:
            raise InvalidParameter('Speech recognition has started.')

        self._start_stream_timestamp = -1
        self._first_package_timestamp = -1
        self._stop_stream_timestamp = -1
        self._on_complete_timestamp = -1
        self._phrase = phrase_id
        self._kwargs.update(**kwargs)
        self._recognition_once = False
        self._worker = threading.Thread(target=self.__receive_worker)
        self._worker.start()
        if self._worker.is_alive():
            self._running = True
            self._callback.on_open()

            # If audio data is not received for 23 seconds, the timeout exits
            self._silence_timer = Timer(Recognition.SILENCE_TIMEOUT_S,
                                        self._silence_stop_timer)
            self._silence_timer.start()
        else:
            self._running = False
            raise InvalidTask('Invalid task, task create failed.')

    def call(self,
             file: str,
             phrase_id: str = None,
             **kwargs) -> RecognitionResult:
        """Real-time speech recognition in synchronous mode.

        Args:
            file (str): The path to the local audio file.
            phrase_id (str, `optional`): The ID of phrase.

            **kwargs:
                disfluency_removal_enabled(bool, `optional`):
                    Filter mood words, turned off by default.
                diarization_enabled (bool, `optional`):
                    Speech auto diarization, turned off by default.
                speaker_count (int, `optional`): The number of speakers.
                timestamp_alignment_enabled (bool, `optional`):
                    Timestamp-alignment calibration, turned off by default.
                special_word_filter(str, `optional`): Sensitive word filter.
                audio_event_detection_enabled(bool, `optional`):
                    Audio event detection, turned off by default.

        Raises:
            InvalidParameter: This interface cannot be called again
                if it has already been started.
            InputDataRequired: The supplied file was empty.

        Returns:
            RecognitionResult: The result of speech recognition.
        """
        self._start_stream_timestamp = time.time() * 1000
        if self._running:
            raise InvalidParameter('Speech recognition has been called.')

        if os.path.exists(file):
            if os.path.isdir(file):
                raise IsADirectoryError('Is a directory: ' + file)
        else:
            raise FileNotFoundError('No such file or directory: ' + file)

        self._recognition_once = True
        self._stream_data = Queue()
        self._phrase = phrase_id
        self._kwargs.update(**kwargs)
        error_flag: bool = False
        sentences: List[Any] = []
        usages: List[Any] = []
        response: RecognitionResponse = None
        result: RecognitionResult = None

        try:
            audio_data: bytes = None
            f = open(file, 'rb')
            if os.path.getsize(file):
                while True:
                    audio_data = f.read(12800)
                    if not audio_data:
                        break
                    else:
                        self._stream_data.put(audio_data)
            else:
                raise InputDataRequired(
                    'The supplied file was empty (zero bytes long)')
            f.close()
            self._stop_stream_timestamp = time.time() * 1000
        except Exception as e:
            logger.error(e)
            raise e

        if not self._stream_data.empty():
            self._running = True
            responses = self.__launch_request()
            for part in responses:
                if part.status_code == HTTPStatus.OK:
                    if 'sentence' in part.output:
                        if (self._first_package_timestamp < 0):
                            self._first_package_timestamp = time.time() * 1000
                            logger.debug('first package delay {}'.format(
                                self._first_package_timestamp -
                                self._start_stream_timestamp))
                        sentence = part.output['sentence']
                        logger.debug(
                            'Recv Result [rid:{}]:{}, isEnd: {}'.format(
                                part.request_id, sentence,
                                RecognitionResult.is_sentence_end(sentence)))
                        if RecognitionResult.is_sentence_end(sentence):
                            sentences.append(sentence)

                            if part.usage is not None:
                                usage = {
                                    'end_time':
                                    part.output['sentence']['end_time'],
                                    'usage': part.usage
                                }
                                usages.append(usage)

                    response = RecognitionResponse.from_api_response(part)
                else:
                    response = RecognitionResponse.from_api_response(part)
                    logger.error(response)
                    error_flag = True
                    break

        self._on_complete_timestamp = time.time() * 1000
        logger.debug('last package delay {}'.format(
            self.get_last_package_delay()))

        if error_flag:
            result = RecognitionResult(response)
        else:
            result = RecognitionResult(response, sentences, usages)

        self._stream_data = Queue()
        self._recognition_once = False
        self._running = False

        return result

    def stop(self):
        """End asynchronous speech recognition.

        Raises:
            InvalidParameter: Cannot stop an uninitiated recognition.
        """
        if self._running is False:
            raise InvalidParameter('Speech recognition has stopped.')

        self._stop_stream_timestamp = time.time() * 1000

        self._running = False
        if self._worker is not None and self._worker.is_alive():
            self._worker.join()
        self._stream_data = Queue()
        if self._silence_timer is not None and self._silence_timer.is_alive():
            self._silence_timer.cancel()
            self._silence_timer = None
        if self._callback:
            self._callback.on_close()

    def send_audio_frame(self, buffer: bytes):
        """Push speech recognition.

        Raises:
            InvalidParameter: Cannot send data to an uninitiated recognition.
        """
        if self._running is False:
            raise InvalidParameter('Speech recognition has stopped.')

        if (self._start_stream_timestamp < 0):
            self._start_stream_timestamp = time.time() * 1000
        logger.debug('send_audio_frame: {}'.format(len(buffer)))
        self._stream_data.put(buffer)

    def _tidy_kwargs(self):
        for k in self._kwargs.copy():
            if self._kwargs[k] is None:
                self._kwargs.pop(k, None)

    def _input_stream_cycle(self):
        while self._running:
            while self._stream_data.empty():
                if self._running:
                    time.sleep(0.01)
                    continue
                else:
                    break

            # Reset silence_timer when getting stream.
            if self._silence_timer is not None and self._silence_timer.is_alive(  # noqa E501
            ):
                self._silence_timer.cancel()
                self._silence_timer = Timer(Recognition.SILENCE_TIMEOUT_S,
                                            self._silence_stop_timer)
                self._silence_timer.start()

            while not self._stream_data.empty():
                frame = self._stream_data.get()
                yield bytes(frame)

            if self._recognition_once:
                self._running = False

        # drain all audio data when invoking stop().
        if self._recognition_once is False:
            while not self._stream_data.empty():
                frame = self._stream_data.get()
                yield bytes(frame)

    def _silence_stop_timer(self):
        """If audio data is not received for a long time, exit worker.
        """
        self._running = False
        if self._silence_timer is not None and self._silence_timer.is_alive():
            self._silence_timer.cancel()
        self._silence_timer = None
        if self._worker is not None and self._worker.is_alive():
            self._worker.join()
        self._stream_data = Queue()

    def get_first_package_delay(self):
        """First Package Delay is the time between start sending audio and receive first words package
        """
        return self._first_package_timestamp - self._start_stream_timestamp

    def get_last_package_delay(self):
        """Last Package Delay is the time between stop sending audio and receive last words package
        """
        return self._on_complete_timestamp - self._stop_stream_timestamp

    # 获取上一个任务的taskId
    def get_last_request_id(self):
        return self.last_request_id
