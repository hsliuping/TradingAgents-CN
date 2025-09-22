# Copyright (c) Alibaba, Inc. and its affiliates.

import json
import platform
import threading
import time
import uuid
from enum import Enum, unique

import dashscope
import websocket
from dashscope.common.error import InputRequired, ModelRequired
from dashscope.common.logging import logger


class QwenTtsRealtimeCallback:
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


class QwenTtsRealtime:
    def __init__(
        self,
        model,
        headers=None,
        callback: QwenTtsRealtimeCallback = None,
        workspace=None,
        url=None,
        additional_params=None,
    ):
        """
        Qwen Tts Realtime SDK
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
        self.last_first_text_time = None
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
            logger.debug('[qwen tts realtime] send string: {}'.format(data))
        self.ws.send(data)

    def update_session(self,
                       voice: str,
                       response_format: AudioFormat = AudioFormat.
                       PCM_24000HZ_MONO_16BIT,
                       mode: str = 'server_commit',
                       **kwargs) -> None:
        '''
        update session configuration, should be used before create response

        Parameters
        ----------
        voice: str
            voice to be used in session
        response_format: AudioFormat
            output audio format
        mode: str
            response mode, server_commit or commit
        '''
        self.config = {
            'voice': voice,
            'mode': mode,
            'response_format': response_format.format,
            'sample_rate': response_format.sample_rate,
        }
        self.config.update(kwargs)
        self.__send_str(
            json.dumps({
                'event_id': self._generate_event_id(),
                'type': 'session.update',
                'session': self.config
            }))

    def append_text(self, text: str) -> None:
        '''
        send text

        Parameters
        ----------
        text: str
            text to send
        '''
        self.__send_str(
            json.dumps({
                'event_id': self._generate_event_id(),
                'type': 'input_text_buffer.append',
                'text': text
            }))
        if self.last_first_text_time is None:
            self.last_first_text_time = time.time() * 1000

    def commit(self, ) -> None:
        '''
        commit the text sent before, create response and start synthesis audio.
        '''
        self.__send_str(
            json.dumps({
                'event_id': self._generate_event_id(),
                'type': 'input_text_buffer.commit'
            }))

    def clear_appended_text(self, ) -> None:
        '''
        clear the text sent to server before.
        '''
        self.__send_str(
            json.dumps({
                'event_id': self._generate_event_id(),
                'type': 'input_text_buffer.clear'
            }))

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

    def finish(self, ) -> None:
        '''
        finish input text stream, server will synthesis all text in buffer and close the connection
        '''
        self.__send_str(
            json.dumps({
                'event_id': self._generate_event_id(),
                'type': 'session.finish'
            }))

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
                    elif 'response.audio.delta' == json_data['type']:
                        if self.last_first_text_time and self.last_first_audio_delay is None:
                            self.last_first_audio_delay = time.time(
                            ) * 1000 - self.last_first_text_time
                    elif 'response.done' == json_data['type']:
                        logger.debug(
                            '[Metric] response: {}, first audio delay: {}'
                            .format(self.last_response_id,
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
        logger.debug(
            '[omni realtime] connection closed with code {} and message {}'.format(
                close_status_code, close_msg))
        self.callback.on_close(close_status_code, close_msg)

    # WebSocket发生错误的回调函数
    def on_error(self, ws, error):
        print(f'websocket closed due to {error}')
        raise Exception(f'websocket closed due to {error}')

    # 获取上一个任务的taskId
    def get_session_id(self):
        return self.session_id

    def get_last_message(self):
        return self.last_message

    def get_last_response_id(self):
        return self.last_response_id

    def get_first_audio_delay(self):
        return self.last_first_audio_delay
