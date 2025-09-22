# Copyright (c) Alibaba, Inc. and its affiliates.

import json
import platform
import threading
import time
from typing import List
import uuid
from enum import Enum, unique

import dashscope
import websocket
from dashscope.common.error import InputRequired, ModelRequired
from dashscope.common.logging import logger


class OmniRealtimeCallback:
    """
    An interface that defines callback methods for getting omni-realtime results. # noqa E501
    Derive from this class and implement its function to provide your own data.
    """
    def on_open(self) -> None:
        pass

    def on_close(self, close_status_code, close_msg) -> None:
        pass

    def on_event(self, message: str) -> None:
        pass


@unique
class AudioFormat(Enum):
    # format, sample_rate, channels, bit_rate, name
    PCM_16000HZ_MONO_16BIT = ('pcm', 16000, 'mono', '16bit', 'pcm16')
    PCM_24000HZ_MONO_16BIT = ('pcm', 24000, 'mono', '16bit', 'pcm16')

    def __init__(self, format, sample_rate, channels, bit_rate, format_str):
        self.format = format
        self.sample_rate = sample_rate
        self.channels = channels
        self.bit_rate = bit_rate
        self.format_str = format_str

    def __repr__(self):
        return self.format_str

    def __str__(self):
        return f'{self.format.upper()} with {self.sample_rate}Hz sample rate, {self.channels} channel, {self.bit_rate} bit rate:  {self.format_str}'


class MultiModality(Enum):
    """
    MultiModality
    """
    TEXT = 'text'
    AUDIO = 'audio'

    def __str__(self):
        return self.name


class OmniRealtimeConversation:
    def __init__(
        self,
        model,
        callback: OmniRealtimeCallback,
        headers=None,
        workspace=None,
        url=None,
        additional_params=None,
    ):
        """
        Qwen Omni Realtime SDK
        Parameters:
        -----------
        model: str
            Model name.
        headers: Dict
            User-defined headers.
        callback: OmniRealtimeCallback
            Callback to receive real-time omni results.
        workspace: str
            Dashscope workspace ID.
        url: str
            Dashscope WebSocket URL.
        additional_params: Dict
            Additional parameters for the Dashscope API.
        """

        if model is None:
            raise ModelRequired('Model is required!')
        if callback is None:
            raise ModelRequired('Callback is required!')
        if url is None:
            url = f'wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={model}'
        else:
            url = f'{url}?model={model}'
        self.url = url
        self.apikey = dashscope.api_key
        self.user_headers = headers
        self.user_workspace = workspace
        self.model = model
        self.config = {}
        self.callback = callback
        self.ws = None
        self.session_id = None
        self.last_message = None
        self.last_response_id = None
        self.last_response_create_time = None
        self.last_first_text_delay = None
        self.last_first_audio_delay = None
        self.metrics = []

    def _generate_event_id(self):
        '''
        generate random event id: event_xxxx
        '''
        return 'event_' + uuid.uuid4().hex

    def _get_websocket_header(self, ):
        ua = 'dashscope/%s; python/%s; platform/%s; processor/%s' % (
            '1.18.0',  # dashscope version
            platform.python_version(),
            platform.platform(),
            platform.processor(),
        )
        headers = {
            'user-agent': ua,
            'Authorization': 'bearer ' + self.apikey,
        }
        if self.user_headers:
            headers = {**self.user_headers, **headers}
        if self.user_workspace:
            headers = {
                **headers,
                'X-DashScope-WorkSpace': self.user_workspace,
            }
        return headers

    def connect(self) -> None:
        '''
        connect to server, create session and return default session configuration
        '''
        self.ws = websocket.WebSocketApp(
            self.url,
            header=self._get_websocket_header(),
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        self.thread = threading.Thread(target=self.ws.run_forever)
        self.thread.daemon = True
        self.thread.start()
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
        self.callback.on_open()

    def __send_str(self, data: str, enable_log: bool = True):
        if enable_log:
            logger.debug('[omni realtime] send string: {}'.format(data))
        self.ws.send(data)

    def update_session(self,
                       output_modalities: List[MultiModality],
                       voice: str,
                       input_audio_format: AudioFormat = AudioFormat.
                       PCM_16000HZ_MONO_16BIT,
                       output_audio_format: AudioFormat = AudioFormat.
                       PCM_24000HZ_MONO_16BIT,
                       enable_input_audio_transcription: bool = True,
                       input_audio_transcription_model: str = None,
                       enable_turn_detection: bool = True,
                       turn_detection_type: str = 'server_vad',
                       prefix_padding_ms: int = 300,
                       turn_detection_threshold: float = 0.2,
                       turn_detection_silence_duration_ms: int = 800,
                       turn_detection_param: dict = None,
                       **kwargs) -> None:
        '''
        update session configuration, should be used before create response

        Parameters
        ----------
        output_modalities: list[MultiModality]
            omni output modalities to be used in session
        voice: str
            voice to be used in session
        input_audio_format: AudioFormat
            input audio format
        output_audio_format: AudioFormat
            output audio format
        enable_turn_detection: bool
            enable turn detection
        turn_detection_threshold: float
            turn detection threshold, range [-1, 1]
            In a noisy environment, it may be necessary to increase the threshold to reduce false detections
            In a quiet environment, it may be necessary to decrease the threshold to improve sensitivity
        turn_detection_silence_duration_ms: int
            duration of silence in milliseconds to detect turn, range [200, 6000]
        '''
        self.config = {
            'modalities': [m.value for m in output_modalities],
            'voice': voice,
            'input_audio_format': input_audio_format.format_str,
            'output_audio_format': output_audio_format.format_str,
        }
        if enable_input_audio_transcription:
            self.config['input_audio_transcription'] = {
                'model': input_audio_transcription_model,
            }
        else:
            self.config['input_audio_transcription'] = None
        if enable_turn_detection:
            self.config['turn_detection'] = {
                'type': turn_detection_type,
                'threshold': turn_detection_threshold,
                'prefix_padding_ms': prefix_padding_ms,
                'silence_duration_ms': turn_detection_silence_duration_ms,
            }
            if turn_detection_param is not None:
                self.config['turn_detection'].update(turn_detection_param)
        else:
            self.config['turn_detection'] = None
        self.config.update(kwargs)
        self.__send_str(
            json.dumps({
                'event_id': self._generate_event_id(),
                'type': 'session.update',
                'session': self.config
            }))

    def append_audio(self, audio_b64: str) -> None:
        '''
        send audio in base64 format

        Parameters
        ----------
        audio_b64: str
            base64 audio string
        '''
        logger.debug('[omni realtime] append audio: {}'.format(len(audio_b64)))
        self.__send_str(
            json.dumps({
                'event_id': self._generate_event_id(),
                'type': 'input_audio_buffer.append',
                'audio': audio_b64
            }), False)

    def append_video(self, video_b64: str) -> None:
        '''
        send one image frame in video in base64 format

        Parameters
        ----------
        video_b64: str
            base64 image string
        '''
        logger.debug('[omni realtime] append video: {}'.format(len(video_b64)))
        self.__send_str(
            json.dumps({
                'event_id': self._generate_event_id(),
                'type': 'input_image_buffer.append',
                'image': video_b64
            }), False)

    def commit(self, ) -> None:
        '''
        Commit the audio and video sent before.
        When in Server VAD mode, the client does not need to use this method,
        the server will commit the audio automatically after detecting vad end.
        '''
        self.__send_str(
            json.dumps({
                'event_id': self._generate_event_id(),
                'type': 'input_audio_buffer.commit'
            }))

    def clear_appended_audio(self, ) -> None:
        '''
        clear the audio sent to server before.
        '''
        self.__send_str(
            json.dumps({
                'event_id': self._generate_event_id(),
                'type': 'input_audio_buffer.clear'
            }))

    def create_response(self,
                        instructions: str = None,
                        output_modalities: List[MultiModality] = None) -> None:
        '''
        create response, use audio and video commited before to request llm.
        When in Server VAD mode, the client does not need to use this method,
        the server will create response automatically after detecting vad
        and sending commit.

        Parameters
        ----------
        instructions: str
            instructions to llm
        output_modalities: list[MultiModality]
            omni output modalities to be used in session
        '''
        request = {
            'event_id': self._generate_event_id(),
            'type': 'response.create',
            'response': {}
        }
        request['response']['instructions'] = instructions
        if output_modalities:
            request['response']['modalities'] = [
                m.value for m in output_modalities
            ]
        self.__send_str(json.dumps(request))

    def cancel_response(self, ) -> None:
        '''
        cancel the current response
        '''
        self.__send_str(
            json.dumps({
                'event_id': self._generate_event_id(),
                'type': 'response.cancel'
            }))

    def send_raw(self, raw_data: str) -> None:
        '''
        send raw data to server
        '''
        self.__send_str(raw_data)

    def close(self, ) -> None:
        '''
        close the connection to server
        '''
        self.ws.close()

    # 监听消息的回调函数
    def on_message(self, ws, message):
        if isinstance(message, str):
            logger.debug('[omni realtime] receive string {}'.format(
                message[:1024]))
            try:
                # 尝试将消息解析为JSON
                json_data = json.loads(message)
                self.last_message = json_data
                self.callback.on_event(json_data)
                if 'type' in message:
                    if 'session.created' == json_data['type']:
                        self.session_id = json_data['session']['id']
                    if 'response.created' == json_data['type']:
                        self.last_response_id = json_data['response']['id']
                        self.last_response_create_time = time.time() * 1000
                        self.last_first_audio_delay = None
                        self.last_first_text_delay = None
                    elif 'response.audio_transcript.delta' == json_data[
                            'type']:
                        if self.last_response_create_time and self.last_first_text_delay is None:
                            self.last_first_text_delay = time.time(
                            ) * 1000 - self.last_response_create_time
                    elif 'response.audio.delta' == json_data['type']:
                        if self.last_response_create_time and self.last_first_audio_delay is None:
                            self.last_first_audio_delay = time.time(
                            ) * 1000 - self.last_response_create_time
                    elif 'response.done' == json_data['type']:
                        logger.info(
                            '[Metric] response: {}, first text delay: {}, first audio delay: {}'
                            .format(self.last_response_id,
                                    self.last_first_text_delay,
                                    self.last_first_audio_delay))
            except json.JSONDecodeError:
                logger.error('Failed to parse message as JSON.')
                raise Exception('Failed to parse message as JSON.')
        elif isinstance(message, (bytes, bytearray)):
            # 如果失败，认为是二进制消息
            logger.error(
                'should not receive binary message in omni realtime api')
            logger.debug('[omni realtime] receive binary {} bytes'.format(
                len(message)))

    def on_close(self, ws, close_status_code, close_msg):
        self.callback.on_close(close_status_code, close_msg)

    # WebSocket发生错误的回调函数
    def on_error(self, ws, error):
        print(f'websocket closed due to {error}')
        raise Exception(f'websocket closed due to {error}')

    # 获取上一个任务的taskId
    def get_session_id(self) -> str:
        return self.session_id

    def get_last_message(self) -> str:
        return self.last_message

    def get_last_message(self) -> str:
        return self.last_message

    def get_last_response_id(self) -> str:
        return self.last_response_id

    def get_last_first_text_delay(self):
        return self.last_first_text_delay

    def get_last_first_audio_delay(self):
        return self.last_first_audio_delay
