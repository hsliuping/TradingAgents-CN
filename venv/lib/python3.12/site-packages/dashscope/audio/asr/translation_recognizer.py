# Copyright (c) Alibaba, Inc. and its affiliates.

import json
import os
import threading
import time
import uuid
from http import HTTPStatus
from queue import Queue
from threading import Timer
from typing import Any, Dict, List

from dashscope.client.base_api import BaseApi
from dashscope.common.constants import ApiProtocol
from dashscope.common.error import (InputDataRequired, InputRequired,
                                    InvalidParameter, InvalidTask,
                                    ModelRequired)
from dashscope.common.logging import logger
from dashscope.common.utils import _get_task_group_and_task
from dashscope.protocol.websocket import WebsocketStreamingMode

DASHSCOPE_TRANSLATION_KEY = 'translations'
DASHSCOPE_TRANSCRIPTION_KEY = 'transcription'


class ThreadSafeBool:
    def __init__(self, initial_value=False):
        self._value = initial_value
        self._lock = threading.Lock()

    def set(self, value):
        with self._lock:
            self._value = value

    def get(self):
        with self._lock:
            return self._value


class WordObj():
    def __init__(self, ) -> None:
        self.text: str = None
        self.begin_time: int = None
        self.end_time: int = None
        self.fixed: bool = False
        self._raw_data = None

    @staticmethod
    def from_json(json_data: Dict[str, Any]):
        """Create a Word object from a JSON dictionary.
        """
        word = WordObj()
        word.text = json_data['text']
        word.begin_time = json_data['begin_time']
        word.end_time = json_data['end_time']
        word.fixed = json_data['fixed']
        word._raw_data = json_data
        return word

    def __str__(self) -> str:
        return 'Word: ' + json.dumps(self._raw_data, ensure_ascii=False)

    def __repr__(self):
        return self.__str__()


class SentenceBaseObj():
    def __init__(self, ) -> None:
        self.sentence_id: int = -1
        self.text: str = None
        self.begin_time: int = None
        self.end_time: int = None
        self.words: List[WordObj] = []
        self._raw_data = None

    @staticmethod
    def from_json(json_data: Dict[str, Any]):
        """Create a SentenceBase object from a JSON dictionary.
        """
        sentence = SentenceBaseObj()
        sentence.sentence_id = json_data['sentence_id']
        sentence.text = json_data['text']
        sentence.begin_time = json_data['begin_time']
        if json_data.get('end_time') is not None:
            sentence.end_time = json_data['end_time']
        else:
            sentence.end_time = json_data['current_time']
        sentence.words = [
            WordObj.from_json(word) for word in json_data['words']
        ]
        sentence._raw_data = json_data
        return sentence

    def __str__(self) -> str:
        return json.dumps(self._raw_data, ensure_ascii=False)

    def __repr__(self):
        return self.__str__()


class TranscriptionResult(SentenceBaseObj):
    def __init__(self, ) -> None:
        self.stash: SentenceBaseObj = None
        self.is_sentence_end = False
        # vad related
        self.vad_pre_end: bool = False
        self.pre_end_failed: bool = False
        self.pre_end_timemillis: int = -1
        self.pre_end_start_time: int = -1
        self.pre_end_end_time: int = -1
        self._raw_data = None

    @staticmethod
    def from_json(json_data: Dict[str, Any]):
        """Create a TranscriptionResult object from a JSON dictionary.
        """
        transcription = TranscriptionResult()
        transcription.sentence_id = json_data['sentence_id']
        transcription.text = json_data['text']
        transcription.begin_time = json_data['begin_time']
        if json_data.get('end_time') is not None:
            transcription.end_time = json_data['end_time']
        else:
            transcription.end_time = json_data['current_time']
        transcription.words = [
            WordObj.from_json(word) for word in json_data['words']
        ]
        transcription._raw_data = json_data
        transcription.is_sentence_end = json_data.get('sentence_end')
        if 'stash' in json_data:
            transcription.stash = SentenceBaseObj.from_json(json_data['stash'])
        if 'vad_pre_end' in json_data:
            transcription.vad_pre_end = json_data['vad_pre_end']
        if 'pre_end_failed' in json_data:
            transcription.pre_end_failed = json_data['pre_end_failed']
        if 'pre_end_start_time' in json_data:
            transcription.pre_end_start_time = json_data['pre_end_start_time']
        if 'pre_end_end_time' in json_data:
            transcription.pre_end_end_time = json_data['pre_end_end_time']
        transcription._raw_data = json_data
        return transcription

    def __str__(self) -> str:
        return 'Transcriptions: ' + json.dumps(self._raw_data,
                                               ensure_ascii=False)

    def __repr__(self):
        return self.__str__()


class Translation(SentenceBaseObj):
    def __init__(self, ) -> None:
        self.language: str = None
        self.stash: SentenceBaseObj = None
        self.is_sentence_end = False
        # vad related
        self.vad_pre_end: bool = False
        self.pre_end_failed: bool = False
        self.pre_end_timemillis: int = -1
        self.pre_end_start_time: int = -1
        self.pre_end_end_time: int = -1
        self._raw_data = None

    @staticmethod
    def from_json(json_data: Dict[str, Any]):
        """Create a Translation object from a JSON dictionary.
        """
        translation = Translation()
        translation.sentence_id = json_data['sentence_id']
        translation.text = json_data['text']
        translation.begin_time = json_data['begin_time']
        if json_data.get('end_time') is not None:
            translation.end_time = json_data['end_time']
        else:
            translation.end_time = json_data['current_time']
        translation.words = [
            WordObj.from_json(word) for word in json_data['words']
        ]
        translation._raw_data = json_data

        translation.language = json_data['lang']
        translation.is_sentence_end = json_data.get('sentence_end')
        if 'stash' in json_data:
            translation.stash = SentenceBaseObj.from_json(json_data['stash'])
        if 'vad_pre_end' in json_data:
            translation.vad_pre_end = json_data['vad_pre_end']
        if 'pre_end_failed' in json_data:
            translation.pre_end_failed = json_data['pre_end_failed']
        if 'pre_end_start_time' in json_data:
            translation.pre_end_start_time = json_data['pre_end_start_time']
        if 'pre_end_end_time' in json_data:
            translation.pre_end_end_time = json_data['pre_end_end_time']
        translation._raw_data = json_data
        return translation

    def __str__(self) -> str:
        return 'Translation: ' + json.dumps(self._raw_data, ensure_ascii=False)

    def __repr__(self):
        return self.__str__()


class TranslationResult():
    def __init__(self, ) -> None:
        self.translations: Dict[str:Translation] = {}
        self.is_sentence_end = False
        self._raw_data = None

    def get_translation(self, language) -> Translation:
        if self.translations is None:
            return None
        return self.translations.get(language)

    def get_language_list(self, ) -> List[str]:
        if self.translations is None:
            return None
        return list(self.translations.keys())

    @staticmethod
    def from_json(json_data: List):
        """Create a TranslationResult object from a JSON dictionary.
        """
        result = TranslationResult()
        result._raw_data = json_data
        for translation_json in json_data:
            if not isinstance(translation_json, dict):
                raise InvalidParameter(
                    f'Invalid translation json data: {translation_json}')
            else:
                translation = Translation.from_json(translation_json)
                result.translations[translation.language] = translation
                if translation.is_sentence_end:
                    result.is_sentence_end = True
        return result

    def __str__(self) -> str:
        return 'TranslationList: ' + json.dumps(self._raw_data,
                                                ensure_ascii=False)

    def __repr__(self):
        return self.__str__()


class TranslationRecognizerResultPack():
    def __init__(self) -> None:
        self.transcription_result_list: List[TranscriptionResult] = []
        self.translation_result_list: List[TranslationResult] = []
        self.usage_list: List = []
        self.request_id: str = None
        self.error_message = None


class TranslationRecognizerCallback():
    """An interface that defines callback methods for getting translation recognizer results. # noqa E501
       Derive from this class and implement its function to provide your own data.
    """
    def on_open(self) -> None:
        pass

    def on_complete(self) -> None:
        pass

    def on_error(self, message) -> None:
        pass

    def on_close(self) -> None:
        pass

    def on_event(self, request_id, transcription_result: TranscriptionResult,
                 translation_result: TranslationResult, usage) -> None:
        pass


class TranslationRecognizerRealtime(BaseApi):
    """TranslationRecognizerRealtime interface.

    Args:
        model (str): The requested model_id.
        callback (TranslationRecognizerRealtime): A callback that returns
            TranslationRecognizerRealtime results.
        format (str): The input audio format.
        sample_rate (int): The input audio sample rate.
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
                 callback: TranslationRecognizerCallback,
                 format: str,
                 sample_rate: int,
                 transcription_enabled: bool = True,
                 source_language: str = None,
                 translation_enabled: bool = False,
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
        self.source_language = source_language
        self.transcription_enabled = transcription_enabled
        self.translation_enabled = translation_enabled
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
        """Asynchronously, initiate a real-time transltion recognizer request and
           obtain the result for parsing.
        """
        responses = self.__launch_request()
        for part in responses:
            if part.status_code == HTTPStatus.OK:
                logger.debug('Received response request_id: {} {}'.format(
                    part.request_id, part.output))
                if len(part.output) == 0:
                    self._on_complete_timestamp = time.time() * 1000
                    logger.debug('last package delay {}'.format(
                        self.get_last_package_delay()))
                    self._callback.on_complete()
                else:
                    usage = None
                    transcription = None
                    translations = None
                    if DASHSCOPE_TRANSCRIPTION_KEY in part.output:
                        transcription = TranscriptionResult.from_json(
                            part.output[DASHSCOPE_TRANSCRIPTION_KEY])
                    if DASHSCOPE_TRANSLATION_KEY in part.output:
                        translations = TranslationResult.from_json(
                            part.output[DASHSCOPE_TRANSLATION_KEY])
                    if transcription is not None or translations is not None:
                        if (self._first_package_timestamp < 0):
                            self._first_package_timestamp = time.time() * 1000
                            logger.debug('first package delay {}'.format(
                                self.get_first_package_delay()))

                    if part.usage is not None:
                        usage = part.usage
                    if self.request_id_confirmed is False and part.request_id is not None:
                        self.last_request_id = part.request_id
                        self.request_id_confirmed = True
                    self._callback.on_event(part.request_id, transcription,
                                            translations, usage)
            else:
                self._running = False
                self._stream_data = Queue()
                self._callback.on_error(part)
                self._callback.on_close()
                break

    def __launch_request(self):
        """Initiate real-time translation recognizer requests.
        """

        self._tidy_kwargs()
        task_name, _ = _get_task_group_and_task(__name__)
        responses = super().call(
            model=self.model,
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
            source_language=self.source_language,
            transcription_enabled=self.transcription_enabled,
            translation_enabled=self.translation_enabled,
            workspace=self._workspace,
            pre_task_id=self.last_request_id,
            **self._kwargs)
        return responses

    def start(self, **kwargs):
        """Real-time translation recognizer in asynchronous mode.
           Please call 'stop()' after you have completed translation & recognition.

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
        assert self._callback is not None, 'Please set the callback to get the translation & recognition result.'  # noqa E501

        if self._running:
            raise InvalidParameter(
                'TranslationRecognizerRealtime has started.')

        self._start_stream_timestamp = -1
        self._first_package_timestamp = -1
        self._stop_stream_timestamp = -1
        self._on_complete_timestamp = -1
        self._kwargs.update(**kwargs)
        self._recognition_once = False
        self._worker = threading.Thread(target=self.__receive_worker)
        self._worker.start()
        if self._worker.is_alive():
            self._running = True
            self._callback.on_open()

            # If audio data is not received for 23 seconds, the timeout exits
            self._silence_timer = Timer(
                TranslationRecognizerRealtime.SILENCE_TIMEOUT_S,
                self._silence_stop_timer)
            self._silence_timer.start()
        else:
            self._running = False
            raise InvalidTask('Invalid task, task create failed.')

    def call(self,
             file: str,
             phrase_id: str = None,
             **kwargs) -> TranslationRecognizerResultPack:
        """TranslationRecognizerRealtime in synchronous mode.

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
            TranslationRecognizerResultPack: The result of speech translation & recognition.
        """
        self._start_stream_timestamp = time.time() * 1000
        if self._running:
            raise InvalidParameter(
                'TranslationRecognizerRealtime has been called.')

        if os.path.exists(file):
            if os.path.isdir(file):
                raise IsADirectoryError('Is a directory: ' + file)
        else:
            raise FileNotFoundError('No such file or directory: ' + file)

        self._recognition_once = True
        self._stream_data = Queue()
        self._phrase = phrase_id
        self._kwargs.update(**kwargs)
        results = TranslationRecognizerResultPack()
        error_message = None

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
                    logger.debug('received data: {}'.format(part.output))
                    # debug log cal fpd
                    transcription = None
                    translation = None
                    usage = None
                    if ('translation' in part.output) or ('transcription'
                                                          in part.output):
                        if (self._first_package_timestamp < 0):
                            self._first_package_timestamp = time.time() * 1000
                            logger.debug('first package delay {}'.format(
                                self._first_package_timestamp -
                                self._start_stream_timestamp))
                        if part.usage is not None:
                            usage = part.usage

                    if DASHSCOPE_TRANSCRIPTION_KEY in part.output:
                        transcription = TranscriptionResult.from_json(
                            part.output[DASHSCOPE_TRANSCRIPTION_KEY])

                    if DASHSCOPE_TRANSLATION_KEY in part.output:
                        translation = TranslationResult.from_json(
                            part.output[DASHSCOPE_TRANSLATION_KEY])

                    if (transcription is not None
                            and transcription.is_sentence_end) or (
                                translation is not None
                                and translation.is_sentence_end):
                        results.request_id = part.request_id
                        results.transcription_result_list.append(transcription)
                        results.translation_result_list.append(translation)
                        results.usage_list.append(usage)
                else:
                    error_message = part
                    logger.error(error_message)
                    break

        self._on_complete_timestamp = time.time() * 1000
        logger.debug('last package delay {}'.format(
            self.get_last_package_delay()))

        self._stream_data = Queue()
        self._recognition_once = False
        self._running = False
        results.error_message = error_message
        return results

    def stop(self):
        """End asynchronous TranslationRecognizerRealtime.

        Raises:
            InvalidParameter: Cannot stop an uninitiated TranslationRecognizerRealtime.
        """
        if self._running is False:
            raise InvalidParameter(
                'TranslationRecognizerRealtime has stopped.')

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
        """Push audio to TranslationRecognizerRealtime.

        Raises:
            InvalidParameter: Cannot send data to an uninitiated TranslationRecognizerRealtime.
        """
        if self._running is False:
            raise InvalidParameter(
                'TranslationRecognizerRealtime has stopped.')

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
                self._silence_timer = Timer(
                    TranslationRecognizerRealtime.SILENCE_TIMEOUT_S,
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


class TranslationRecognizerChat(BaseApi):
    """TranslationRecognizerChat interface.

    Args:
        model (str): The requested model_id.
        callback (TranslationRecognizerChat): A callback that returns
            TranslationRecognizerChat results.
        format (str): The input audio format.
        sample_rate (int): The input audio sample rate.
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
                 callback: TranslationRecognizerCallback,
                 format: str,
                 sample_rate: int,
                 transcription_enabled: bool = True,
                 source_language: str = None,
                 translation_enabled: bool = False,
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
        self.source_language = source_language
        self.transcription_enabled = transcription_enabled
        self.translation_enabled = translation_enabled
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
        self._is_sentence_end = ThreadSafeBool(False)

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
        """Asynchronously, initiate a real-time transltion recognizer request and
           obtain the result for parsing.
        """
        responses = self.__launch_request()
        for part in responses:
            if part.status_code == HTTPStatus.OK:
                logger.debug('Received response request_id: {} {}'.format(
                    part.request_id, part.output))
                if len(part.output) == 0:
                    self._on_complete_timestamp = time.time() * 1000
                    logger.debug('last package delay {}'.format(
                        self.get_last_package_delay()))
                    self._callback.on_complete()
                else:
                    usage = None
                    transcription = None
                    translations = None
                    if DASHSCOPE_TRANSCRIPTION_KEY in part.output:
                        transcription = TranscriptionResult.from_json(
                            part.output[DASHSCOPE_TRANSCRIPTION_KEY])
                    if DASHSCOPE_TRANSLATION_KEY in part.output:
                        translations = TranslationResult.from_json(
                            part.output[DASHSCOPE_TRANSLATION_KEY])
                    if transcription is not None or translations is not None:
                        if (self._first_package_timestamp < 0):
                            self._first_package_timestamp = time.time() * 1000
                            logger.debug('first package delay {}'.format(
                                self.get_first_package_delay()))

                    if part.usage is not None:
                        usage = part.usage
                    if self.request_id_confirmed is False and part.request_id is not None:
                        self.last_request_id = part.request_id
                        self.request_id_confirmed = True
                    if transcription is not None and transcription.is_sentence_end:
                        logger.debug(
                            '[Chat] recv sentence end in transcription, stop asr'
                        )
                        self._is_sentence_end.set(True)
                    if translations is not None and translations.is_sentence_end:
                        logger.debug(
                            '[Chat] recv sentence end in translation, stop asr'
                        )
                        self._is_sentence_end.set(True)
                    self._callback.on_event(part.request_id, transcription,
                                            translations, usage)
            else:
                self._running = False
                self._stream_data = Queue()
                self._callback.on_error(part)
                self._callback.on_close()
                break

    def __launch_request(self):
        """Initiate real-time translation recognizer requests.
        """

        self._tidy_kwargs()
        task_name, _ = _get_task_group_and_task(__name__)
        responses = super().call(
            model=self.model,
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
            source_language=self.source_language,
            transcription_enabled=self.transcription_enabled,
            translation_enabled=self.translation_enabled,
            workspace=self._workspace,
            pre_task_id=self.last_request_id,
            **self._kwargs)
        return responses

    def start(self, **kwargs):
        """Real-time translation recognizer in asynchronous mode.
           Please call 'stop()' after you have completed translation & recognition.

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
        assert self._callback is not None, 'Please set the callback to get the translation & recognition result.'  # noqa E501

        if self._running:
            raise InvalidParameter('TranslationRecognizerChat has started.')

        self._start_stream_timestamp = -1
        self._first_package_timestamp = -1
        self._stop_stream_timestamp = -1
        self._on_complete_timestamp = -1
        self._kwargs.update(**kwargs)
        self._recognition_once = False
        self._worker = threading.Thread(target=self.__receive_worker)
        self._worker.start()
        if self._worker.is_alive():
            self._running = True
            self._callback.on_open()

            # If audio data is not received for 23 seconds, the timeout exits
            self._silence_timer = Timer(
                TranslationRecognizerChat.SILENCE_TIMEOUT_S,
                self._silence_stop_timer)
            self._silence_timer.start()
        else:
            self._running = False
            raise InvalidTask('Invalid task, task create failed.')

    def stop(self):
        """End asynchronous TranslationRecognizerChat.

        Raises:
            InvalidParameter: Cannot stop an uninitiated TranslationRecognizerChat.
        """
        if self._running is False:
            raise InvalidParameter('TranslationRecognizerChat has stopped.')

        self._stop_stream_timestamp = time.time() * 1000
        logger.debug('stop TranslationRecognizerChat')
        self._running = False
        if self._worker is not None and self._worker.is_alive():
            self._worker.join()
        self._stream_data = Queue()
        if self._silence_timer is not None and self._silence_timer.is_alive():
            self._silence_timer.cancel()
            self._silence_timer = None
        if self._callback:
            self._callback.on_close()

    def send_audio_frame(self, buffer: bytes) -> bool:
        """Push audio to TranslationRecognizerChat.

        Raises:
            InvalidParameter: Cannot send data to an uninitiated TranslationRecognizerChat.
        """
        if self._is_sentence_end.get():
            logger.debug('skip audio due to has sentence end.')
            return False

        if self._running is False:
            raise InvalidParameter('TranslationRecognizerChat has stopped.')

        if (self._start_stream_timestamp < 0):
            self._start_stream_timestamp = time.time() * 1000
        logger.debug('send_audio_frame: {}'.format(len(buffer)))
        self._stream_data.put(buffer)
        return True

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
                self._silence_timer = Timer(
                    TranslationRecognizerChat.SILENCE_TIMEOUT_S,
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
