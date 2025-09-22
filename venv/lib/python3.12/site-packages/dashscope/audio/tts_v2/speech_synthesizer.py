# Copyright (c) Alibaba, Inc. and its affiliates.

import json
import platform
import threading
import time
import uuid
from enum import Enum, unique

import websocket

import dashscope
from dashscope.common.error import InputRequired, InvalidTask, ModelRequired
from dashscope.common.logging import logger
from dashscope.protocol.websocket import (ACTION_KEY, EVENT_KEY, HEADER,
                                          TASK_ID, ActionType, EventType,
                                          WebsocketStreamingMode)


class ResultCallback:
    """
    An interface that defines callback methods for getting speech synthesis results. # noqa E501
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

    def on_event(self, message: str) -> None:
        pass

    def on_data(self, data: bytes) -> None:
        pass


@unique
class AudioFormat(Enum):
    DEFAULT = ('Default', 0, '0', 0)
    WAV_8000HZ_MONO_16BIT = ('wav', 8000, 'mono', 0)
    WAV_16000HZ_MONO_16BIT = ('wav', 16000, 'mono', 16)
    WAV_22050HZ_MONO_16BIT = ('wav', 22050, 'mono', 16)
    WAV_24000HZ_MONO_16BIT = ('wav', 24000, 'mono', 16)
    WAV_44100HZ_MONO_16BIT = ('wav', 44100, 'mono', 16)
    WAV_48000HZ_MONO_16BIT = ('wav', 48000, 'mono', 16)

    MP3_8000HZ_MONO_128KBPS = ('mp3', 8000, 'mono', 128)
    MP3_16000HZ_MONO_128KBPS = ('mp3', 16000, 'mono', 128)
    MP3_22050HZ_MONO_256KBPS = ('mp3', 22050, 'mono', 256)
    MP3_24000HZ_MONO_256KBPS = ('mp3', 24000, 'mono', 256)
    MP3_44100HZ_MONO_256KBPS = ('mp3', 44100, 'mono', 256)
    MP3_48000HZ_MONO_256KBPS = ('mp3', 48000, 'mono', 256)

    PCM_8000HZ_MONO_16BIT = ('pcm', 8000, 'mono', 16)
    PCM_16000HZ_MONO_16BIT = ('pcm', 16000, 'mono', 16)
    PCM_22050HZ_MONO_16BIT = ('pcm', 22050, 'mono', 16)
    PCM_24000HZ_MONO_16BIT = ('pcm', 24000, 'mono', 16)
    PCM_44100HZ_MONO_16BIT = ('pcm', 44100, 'mono', 16)
    PCM_48000HZ_MONO_16BIT = ('pcm', 48000, 'mono', 16)

    OGG_OPUS_8KHZ_MONO_32KBPS = ("opus", 8000, "mono", 32)
    OGG_OPUS_8KHZ_MONO_16KBPS = ("opus", 8000, "mono", 16)
    OGG_OPUS_16KHZ_MONO_16KBPS = ("opus", 16000, "mono", 16)
    OGG_OPUS_16KHZ_MONO_32KBPS = ("opus", 16000, "mono", 32)
    OGG_OPUS_16KHZ_MONO_64KBPS = ("opus", 16000, "mono", 64)
    OGG_OPUS_24KHZ_MONO_16KBPS = ("opus", 24000, "mono", 16)
    OGG_OPUS_24KHZ_MONO_32KBPS = ("opus", 24000, "mono", 32)
    OGG_OPUS_24KHZ_MONO_64KBPS = ("opus", 24000, "mono", 64)
    OGG_OPUS_48KHZ_MONO_16KBPS = ("opus", 48000, "mono", 16)
    OGG_OPUS_48KHZ_MONO_32KBPS = ("opus", 48000, "mono", 32)
    OGG_OPUS_48KHZ_MONO_64KBPS = ("opus", 48000, "mono", 64)
    def __init__(self, format, sample_rate, channels, bit_rate):
        self.format = format
        self.sample_rate = sample_rate
        self.channels = channels
        self.bit_rate = bit_rate

    def __str__(self):
        return f'{self.format.upper()} with {self.sample_rate}Hz sample rate, {self.channels} channel, {self.bit_rate}'


class Request:
    def __init__(
        self,
        apikey,
        model,
        voice,
        format='wav',
        sample_rate=16000,
        bit_rate=64000,
        volume=50,
        speech_rate=1.0,
        pitch_rate=1.0,
    ):
        self.task_id = self.genUid()
        self.apikey = apikey
        self.voice = voice
        self.model = model
        self.format = format
        self.sample_rate = sample_rate
        self.bit_rate = bit_rate
        self.volume = volume
        self.speech_rate = speech_rate
        self.pitch_rate = pitch_rate

    def genUid(self):
        # 生成随机UUID
        return uuid.uuid4().hex

    def getWebsocketHeaders(self, headers, workspace):
        ua = 'dashscope/%s; python/%s; platform/%s; processor/%s' % (
            '1.18.0',  # dashscope version
            platform.python_version(),
            platform.platform(),
            platform.processor(),
        )
        self.headers = {
            'user-agent': ua,
            'Authorization': 'bearer ' + self.apikey,
        }
        if headers:
            self.headers = {**self.headers, **headers}
        if workspace:
            self.headers = {
                **self.headers,
                'X-DashScope-WorkSpace': workspace,
            }
        return self.headers

    def getStartRequest(self, additional_params=None):

        cmd = {
            HEADER: {
                ACTION_KEY: ActionType.START,
                TASK_ID: self.task_id,
                'streaming': WebsocketStreamingMode.DUPLEX,
            },
            'payload': {
                'model': self.model,
                'task_group': 'audio',
                'task': 'tts',
                'function': 'SpeechSynthesizer',
                'input': {},
                'parameters': {
                    'voice': self.voice,
                    'volume': self.volume,
                    'text_type': 'PlainText',
                    'sample_rate': self.sample_rate,
                    'rate': self.speech_rate,
                    'format': self.format,
                    'pitch': self.pitch_rate,
                },
            },
        }
        if self.format == 'opus':
            cmd['payload']['parameters']['bit_rate'] = self.bit_rate
        if additional_params:
            cmd['payload']['parameters'].update(additional_params)
        return json.dumps(cmd)

    def getContinueRequest(self, text):
        cmd = {
            HEADER: {
                ACTION_KEY: ActionType.CONTINUE,
                TASK_ID: self.task_id,
                'streaming': WebsocketStreamingMode.DUPLEX,
            },
            'payload': {
                'model': self.model,
                'task_group': 'audio',
                'task': 'tts',
                'function': 'SpeechSynthesizer',
                'input': {
                    'text': text
                },
            },
        }
        return json.dumps(cmd)

    def getFinishRequest(self):
        cmd = {
            HEADER: {
                ACTION_KEY: ActionType.FINISHED,
                TASK_ID: self.task_id,
                'streaming': WebsocketStreamingMode.DUPLEX,
            },
            'payload': {
                'input': {},
            },
        }
        return json.dumps(cmd)


class SpeechSynthesizer:
    def __init__(
        self,
        model,
        voice,
        format: AudioFormat = AudioFormat.DEFAULT,
        volume=50,
        speech_rate=1.0,
        pitch_rate=1.0,
        headers=None,
        callback: ResultCallback = None,
        workspace=None,
        url=None,
        additional_params=None,
    ):
        """
        CosyVoice Speech Synthesis SDK
        Parameters:
        -----------
        model: str
            Model name.
        voice: str
            Voice name.
        format: AudioFormat
            Synthesis audio format.
        volume: int
            The volume of the synthesized audio, with a range from 0 to 100. Default is 50.
        rate: float
            The speech rate of the synthesized audio, with a range from 0.5 to 2. Default is 1.0.
        pitch: float
            The pitch of the synthesized audio, with a range from 0.5 to 2. Default is 1.0.
        headers: Dict
            User-defined headers.
        callback: ResultCallback
            Callback to receive real-time synthesis results.
        workspace: str
            Dashscope workspace ID.
        url: str
            Dashscope WebSocket URL.
        additional_params: Dict
            Additional parameters for the Dashscope API.
        """

        if model is None:
            raise ModelRequired('Model is required!')
        if format is None:
            raise InputRequired('format is required!')
        if url is None:
            url = dashscope.base_websocket_api_url
        self.url = url
        self.apikey = dashscope.api_key
        self.headers = headers
        self.workspace = workspace
        self.additional_params = additional_params
        self.model = model
        self.voice = voice
        self.aformat = format.format
        if (self.aformat == 'DEFAULT'):
            self.aformat = 'mp3'
        self.sample_rate = format.sample_rate
        if (self.sample_rate == 0):
            self.sample_rate = 22050

        self.request = Request(
            apikey=self.apikey,
            model=model,
            voice=voice,
            format=format.format,
            sample_rate=format.sample_rate,
            bit_rate = format.bit_rate,
            volume=volume,
            speech_rate=speech_rate,
            pitch_rate=pitch_rate,
        )
        self.last_request_id = self.request.task_id
        self.start_event = threading.Event()
        self.complete_event = threading.Event()
        self._stopped = threading.Event()
        self._audio_data: bytes = None
        self._is_started = False
        self._cancel = False
        self._cancel_lock = threading.Lock()
        self.async_call = True
        self.callback = callback
        self._is_first = True
        self.async_call = True
        # since dashscope sdk will send first text in run-task
        if not self.callback:
            self.async_call = False
        self._start_stream_timestamp = -1
        self._first_package_timestamp = -1
        self._recv_audio_length = 0
        self.last_response = None

    def __send_str(self, data: str):
        logger.debug('>>>send {}'.format(data))
        self.ws.send(data)

    def __start_stream(self, ):
        self._start_stream_timestamp = time.time() * 1000
        self._first_package_timestamp = -1
        self._recv_audio_length = 0
        if self.callback is None:
            raise InputRequired('callback is required!')
        # reset inner params
        self._stopped.clear()
        self._stream_data = ['']
        self._worker = None
        self._audio_data: bytes = None

        if self._is_started:
            raise InvalidTask('task has already started.')

        self.ws = websocket.WebSocketApp(
            self.url,
            header=self.request.getWebsocketHeaders(headers=self.headers,
                                                    workspace=self.workspace),
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        self.thread = threading.Thread(target=self.ws.run_forever)
        self.thread.daemon = True
        self.thread.start()
        request = self.request.getStartRequest(self.additional_params)
        # 等待连接建立
        timeout = 5  # 最长等待时间（秒）
        start_time = time.time()
        while (not (self.ws.sock and self.ws.sock.connected)
               and (time.time() - start_time) < timeout):
            time.sleep(0.1)  # 短暂休眠，避免密集轮询
        if not (self.ws.sock and self.ws.sock.connected):
            raise TimeoutError(
                'websocket connection could not established within 5s. '
                'Please check your network connection, firewall settings, or server status.'
            )
        self.__send_str(request)
        if not self.start_event.wait(10):
            raise TimeoutError('start speech synthesizer failed within 5s.')
        self._is_started = True
        if self.callback:
            self.callback.on_open()

    def __submit_text(self, text):
        if not self._is_started:
            raise InvalidTask('speech synthesizer has not been started.')

        if self._stopped.is_set():
            raise InvalidTask('speech synthesizer task has stopped.')
        request = self.request.getContinueRequest(text)
        self.__send_str(request)

    def streaming_call(self, text: str):
        """
        Streaming input mode: You can call the stream_call function multiple times to send text.
        A session will be created on the first call.
        The session ends after calling streaming_complete.
        Parameters:
        -----------
        text: str
            utf-8 encoded text
        """
        if self._is_first:
            self._is_first = False
            self.__start_stream()
        self.__submit_text(text)
        return None

    def streaming_complete(self, complete_timeout_millis=600000):
        """
        Synchronously stop the streaming input speech synthesis task.
        Wait for all remaining synthesized audio before returning

        Parameters:
        -----------
        complete_timeout_millis: int
            Throws TimeoutError exception if it times out. If the timeout is not None
            and greater than zero, it will wait for the corresponding number of
            milliseconds; otherwise, it will wait indefinitely.
        """
        if not self._is_started:
            raise InvalidTask('speech synthesizer has not been started.')
        if self._stopped.is_set():
            raise InvalidTask('speech synthesizer task has stopped.')
        request = self.request.getFinishRequest()
        self.__send_str(request)
        if complete_timeout_millis is not None and complete_timeout_millis > 0:
            if not self.complete_event.wait(timeout=complete_timeout_millis /
                                            1000):
                raise TimeoutError(
                    'speech synthesizer wait for complete timeout {}ms'.format(
                        complete_timeout_millis))
        else:
            self.complete_event.wait()
        self.close()
        self._stopped.set()
        self._is_started = False

    def __waiting_for_complete(self, timeout):
        if timeout is not None and timeout > 0:
            if not self.complete_event.wait(timeout=timeout / 1000):
                raise TimeoutError(
                    f'speech synthesizer wait for complete timeout {timeout}ms'
                )
        else:
            self.complete_event.wait()
        self.close()
        self._stopped.set()
        self._is_started = False

    def async_streaming_complete(self, complete_timeout_millis=600000):
        """
        Asynchronously stop the streaming input speech synthesis task, returns immediately.
        You need to listen and handle the STREAM_INPUT_TTS_EVENT_SYNTHESIS_COMPLETE event in the on_event callback.
        Do not destroy the object and callback before this event.

        Parameters:
        -----------
        complete_timeout_millis: int
            Throws TimeoutError exception if it times out. If the timeout is not None
            and greater than zero, it will wait for the corresponding number of
            milliseconds; otherwise, it will wait indefinitely.
        """

        if not self._is_started:
            raise InvalidTask('speech synthesizer has not been started.')
        if self._stopped.is_set():
            raise InvalidTask('speech synthesizer task has stopped.')
        request = self.request.getFinishRequest()
        self.__send_str(request)
        thread = threading.Thread(target=self.__waiting_for_complete,
                                  args=(complete_timeout_millis, ))
        thread.start()

    def streaming_cancel(self):
        """
        Immediately terminate the streaming input speech synthesis task
        and discard any remaining audio that is not yet delivered.
        """

        if not self._is_started:
            raise InvalidTask('speech synthesizer has not been started.')
        if self._stopped.is_set():
            return
        request = self.request.getFinishRequest()
        self.__send_str(request)
        self.close()
        self.start_event.set()
        self.complete_event.set()

    # 监听消息的回调函数
    def on_message(self, ws, message):
        if isinstance(message, str):
            logger.debug('<<<recv {}'.format(message))
            try:
                # 尝试将消息解析为JSON
                json_data = json.loads(message)
                self.last_response = json_data
                event = json_data['header'][EVENT_KEY]
                # 调用JSON回调
                if EventType.STARTED == event:
                    self.start_event.set()
                elif EventType.FINISHED == event:
                    self.complete_event.set()
                    if self.callback:
                        self.callback.on_complete()
                        self.callback.on_close()
                elif EventType.FAILED == event:
                    self.start_event.set()
                    self.complete_event.set()
                    if self.async_call:
                        self.callback.on_error(message)
                        self.callback.on_close()
                    else:
                        logger.error(f'TaskFailed: {message}')
                        raise Exception(f'TaskFailed: {message}')
                elif EventType.GENERATED == event:
                    if self.callback:
                        self.callback.on_event(message)
                else:
                    pass
            except json.JSONDecodeError:
                logger.error('Failed to parse message as JSON.')
                raise Exception('Failed to parse message as JSON.')
        elif isinstance(message, (bytes, bytearray)):
            # 如果失败，认为是二进制消息
            logger.debug('<<<recv binary {}'.format(len(message)))
            if (self._recv_audio_length == 0):
                self._first_package_timestamp = time.time() * 1000
                logger.debug('first package delay {}'.format(
                    self._first_package_timestamp -
                    self._start_stream_timestamp))
            self._recv_audio_length += len(message) / (2 * self.sample_rate /
                                                       1000)
            current = time.time() * 1000
            current_rtf = (current - self._start_stream_timestamp
                           ) / self._recv_audio_length
            logger.debug('total audio {} ms, current_rtf: {}'.format(
                self._recv_audio_length, current_rtf))
            # 只有在非异步调用的时候保存音频
            if not self.async_call:
                if self._audio_data is None:
                    self._audio_data = bytes(message)
                else:
                    self._audio_data = self._audio_data + bytes(message)
            if self.callback:
                self.callback.on_data(message)

    def call(self, text: str, timeout_millis=None):
        """
        Speech synthesis.
        If callback is set, the audio will be returned in real-time through the on_event interface.
        Otherwise, this function blocks until all audio is received and then returns the complete audio data.

        Parameters:
        -----------
        text: str
            utf-8 encoded text
        timeoutMillis:
            Integer or None
        return: bytes
            If a callback is not set during initialization, the complete audio is returned
            as the function's return value. Otherwise, the return value is null.
            If the timeout is set to a value greater than zero and not None,
            it will wait for the corresponding number of milliseconds;
            otherwise, it will wait indefinitely.
        """
        # print('还不支持非流式语音合成sdk调用大模型，使用流式模拟')
        if self.additional_params is None:
            self.additional_params = {"enable_ssml":True}
        else:
            self.additional_params["enable_ssml"] = True
        if not self.callback:
            self.callback = ResultCallback()
        self.__start_stream()
        self.__submit_text(text)
        if self.async_call:
            self.async_streaming_complete(timeout_millis)
            return None
        else:
            self.streaming_complete(timeout_millis)
            return self._audio_data

    # WebSocket关闭的回调函数
    def on_close(self, ws, close_status_code, close_msg):
        pass

    # WebSocket发生错误的回调函数
    def on_error(self, ws, error):
        print(f'websocket closed due to {error}')
        raise Exception(f'websocket closed due to {error}')

    # 关闭WebSocket连接
    def close(self):
        self.ws.close()

    # 获取上一个任务的taskId
    def get_last_request_id(self):
        return self.last_request_id

    def get_first_package_delay(self):
        """First Package Delay is the time between start sending text and receive first audio package
        """
        return self._first_package_timestamp - self._start_stream_timestamp

    def get_response(self):
        return self.last_response
