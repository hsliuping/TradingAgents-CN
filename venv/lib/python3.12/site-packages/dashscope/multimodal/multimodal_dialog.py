import json
import platform
import time
import threading
from abc import abstractmethod

import websocket

import dashscope
from dashscope.common.logging import logger
from dashscope.common.error import InputRequired
from dashscope.multimodal import dialog_state
from dashscope.multimodal.multimodal_constants import *
from dashscope.multimodal.multimodal_request_params import RequestParameters, get_random_uuid, DashHeader, \
    RequestBodyInput, DashPayload, RequestToRespondParameters, RequestToRespondBodyInput
from dashscope.protocol.websocket import ActionType


class MultiModalCallback:
    """
    语音聊天回调类，用于处理语音聊天过程中的各种事件。
    """

    def on_started(self, dialog_id: str) -> None:
        """
        通知对话开始

        :param dialog_id: 回调对话ID
        """
        pass

    def on_stopped(self) -> None:
        """
        通知对话停止
        """
        pass

    def on_state_changed(self, state: 'dialog_state.DialogState') -> None:
        """
        对话状态改变

        :param state: 新的对话状态
        """
        pass

    def on_speech_audio_data(self, data: bytes) -> None:
        """
        合成音频数据回调

        :param data: 音频数据
        """
        pass

    def on_error(self, error) -> None:
        """
        发生错误时调用此方法。

        :param error: 错误信息
        """
        pass

    def on_connected(self) -> None:
        """
        成功连接到服务器后调用此方法。
        """
        pass

    def on_responding_started(self):
        """
        回复开始回调
        """
        pass

    def on_responding_ended(self, payload):
        """
        回复结束
        """
        pass

    def on_speech_started(self):
        """
        检测到语音输入结束
        """
        pass

    def on_speech_ended(self):
        """
        检测到语音输入结束
        """
        pass

    def on_speech_content(self, payload):
        """
        语音识别文本

        :param payload: text
        """
        pass

    def on_responding_content(self, payload):
        """
        大模型回复文本。

        :param payload: text
        """
        pass

    def on_request_accepted(self):
        """
        打断请求被接受。
        """
        pass

    def on_close(self, close_status_code, close_msg):
        """
        连接关闭时调用此方法。

        :param close_status_code: 关闭状态码
        :param close_msg: 关闭消息
        """
        pass


class MultiModalDialog:
    """
    用于管理WebSocket连接以进行语音聊天的服务类。
    """

    def __init__(self,
                 app_id: str,
                 request_params: RequestParameters,
                 multimodal_callback: MultiModalCallback,
                 workspace_id: str = None,
                 url: str = None,
                 api_key: str = None,
                 dialog_id: str = None,
                 model: str = None
                 ):
        """
                创建一个语音对话会话。

                此方法用于初始化一个新的voice_chat会话，设置必要的参数以准备开始与模型的交互。
                ：param workspace_id: 客户的workspace_id 主工作空间id,非必填字段
                :param app_id: 客户在管控台创建的应用id，可以根据值规律确定使用哪个对话系统
                :param request_params: 请求参数集合
                :param url: (str) API的URL地址。
                :param multimodal_callback: (MultimodalCallback) 回调对象，用于处理来自服务器的消息。
                :param api_key: (str) 应用程序接入的唯一key
                :param dialog_id:对话id，如果传入表示承接上下文继续聊
                :param model: 模型
        """
        if request_params is None:
            raise InputRequired('request_params is required!')
        if url is None:
            url = dashscope.base_websocket_api_url
        if api_key is None:
            api_key = dashscope.api_key

        self.request_params = request_params
        self.model = model
        self._voice_detection = None
        self.thread = None
        self.ws = None
        self.request = _Request()
        self._callback = multimodal_callback
        self.url = url
        self.api_key = api_key
        self.workspace_id = workspace_id
        self.app_id = app_id
        self.dialog_id = dialog_id
        self.dialog_state = dialog_state.StateMachine()
        self.response = _Response(self.dialog_state, self._callback, self.close)  # 传递 self.close 作为回调

    def _on_message(self, ws, message):
        logger.debug(f"<<<<<<< Received message: {message}")
        if isinstance(message, str):
            self.response.handle_text_response(message)
        elif isinstance(message, (bytes, bytearray)):
            self.response.handle_binary_response(message)

    def _on_error(self, ws, error):
        logger.error(f"Error: {error}")
        if self._callback:
            self._callback.on_error(error)

    def _on_close(self, ws, close_status_code, close_msg):
        try:
            logger.debug(
                "WebSocket connection closed with status {} and message {}".format(close_status_code, close_msg))
            if close_status_code is None:
                close_status_code = 1000
            if close_msg is None:
                close_msg = "websocket is closed"
            self._callback.on_close(close_status_code, close_msg)
        except Exception as e:
            logger.error(f"Error: {e}")

    def _on_open(self, ws):
        self._callback.on_connected()

    # def _on_pong(self, _):
    #     _log.debug("on pong")

    def start(self, dialog_id, enable_voice_detection=False):
        """
        初始化WebSocket连接并发送启动请求
        :param dialog_id: 上下位继承标志位。新对话无需设置。
               如果继承之前的对话历史，则需要记录之前的dialog_id并传入
        :param enable_voice_detection: 是否开启语音检测,可选参数 默认False
        """
        self._voice_detection = enable_voice_detection
        self._connect(self.api_key)
        logger.debug("connected with server.")
        self._send_start_request(dialog_id, self.request_params)

    def start_speech(self):
        """开始上传语音数据"""
        _send_speech_json = self.request.generate_common_direction_request("SendSpeech", self.dialog_id)
        self._send_text_frame(_send_speech_json)

    def send_audio_data(self, speech_data: bytes):
        """发送语音数据"""
        self.__send_binary_frame(speech_data)

    def stop_speech(self):
        """停止上传语音数据"""
        _send_speech_json = self.request.generate_common_direction_request("StopSpeech", self.dialog_id)
        self._send_text_frame(_send_speech_json)

    def interrupt(self):
        """请求服务端开始说话"""
        _send_speech_json = self.request.generate_common_direction_request("RequestToSpeak", self.dialog_id)
        self._send_text_frame(_send_speech_json)

    def request_to_respond(self,
                           request_type: str,
                           text: str,
                           parameters: RequestToRespondParameters = None):
        """请求服务端直接文本合成语音"""
        _send_speech_json = self.request.generate_request_to_response_json(direction_name="RequestToRespond",
                                                                           dialog_id=self.dialog_id,
                                                                           request_type=request_type, text=text,
                                                                           parameters=parameters)
        self._send_text_frame(_send_speech_json)

    @abstractmethod
    def request_to_respond_prompt(self, text):
        """请求服务端通过文本请求回复文本答复"""
        return

    def local_responding_started(self):
        """本地tts播放开始"""
        _send_speech_json = self.request.generate_common_direction_request("LocalRespondingStarted", self.dialog_id)
        self._send_text_frame(_send_speech_json)

    def local_responding_ended(self):
        """本地tts播放结束"""
        _send_speech_json = self.request.generate_common_direction_request("LocalRespondingEnded", self.dialog_id)
        self._send_text_frame(_send_speech_json)

    def send_heart_beat(self):
        """发送心跳"""
        _send_speech_json = self.request.generate_common_direction_request("HeartBeat", self.dialog_id)
        self._send_text_frame(_send_speech_json)

    def update_info(self, parameters: RequestToRespondParameters = None):
        """更新信息"""
        _send_speech_json = self.request.generate_update_info_json(direction_name="UpdateInfo", dialog_id=self.dialog_id, parameters=parameters)
        self._send_text_frame(_send_speech_json)

    def stop(self):
        if self.ws is None or not self.ws.sock or not self.ws.sock.connected:
            self._callback.on_close(1001, "websocket is not connected")
            return
        _send_speech_json = self.request.generate_stop_request("Stop", self.dialog_id)
        self._send_text_frame(_send_speech_json)

    def get_dialog_state(self) -> dialog_state.DialogState:
        return self.dialog_state.get_current_state()

    def get_conversation_mode(self) -> str:
        """get mode of conversation: support tap2talk/push2talk/duplex"""
        return self.request_params.upstream.mode

    """内部方法"""

    def _send_start_request(self, dialog_id: str, request_params: RequestParameters):
        """发送'Start'请求"""
        _start_json = self.request.generate_start_request(
            workspace_id=self.workspace_id,
            direction_name="Start",
            dialog_id=dialog_id,
            app_id=self.app_id,
            request_params=request_params,
            model=self.model
        )
        # send start request
        self._send_text_frame(_start_json)

    def _run_forever(self):
        self.ws.run_forever(ping_interval=5, ping_timeout=4)

    def _connect(self, api_key: str):
        """初始化WebSocket连接并发送启动请求。"""
        self.ws = websocket.WebSocketApp(self.url, header=self.request.get_websocket_header(api_key),
                                         on_open=self._on_open,
                                         on_message=self._on_message,
                                         on_error=self._on_error,
                                         on_close=self._on_close)
        self.thread = threading.Thread(target=self._run_forever)
        self.ws.ping_interval = 3
        self.thread.daemon = True
        self.thread.start()

        self._wait_for_connection()

    def close(self):
        if self.ws is None or not self.ws.sock or not self.ws.sock.connected:
            return
        self.ws.close()

    def _wait_for_connection(self):
        """等待WebSocket连接建立"""
        timeout = 5
        start_time = time.time()
        while not (self.ws.sock and self.ws.sock.connected) and (time.time() - start_time) < timeout:
            time.sleep(0.1)  # 短暂休眠，避免密集轮询

    def _send_text_frame(self, text: str):
        logger.info('>>>>>> send text frame : %s' % text)
        self.ws.send(text, websocket.ABNF.OPCODE_TEXT)

    def __send_binary_frame(self, binary: bytes):
        # _log.info('send binary frame length: %d' % len(binary))
        self.ws.send(binary, websocket.ABNF.OPCODE_BINARY)

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        """清理所有资源"""
        try:
            if self.ws:
                self.ws.close()
            if self.thread and self.thread.is_alive():
                # 设置标志位通知线程退出
                self.thread.join(timeout=2)
            # 清除引用
            self.ws = None
            self.thread = None
            self._callback = None
            self.response = None
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")


class _Request:
    def __init__(self):
        # websocket header
        self.ws_headers = None
        # request body for voice chat
        self.header = None
        self.payload = None
        # params
        self.task_id = None
        self.app_id = None
        self.workspace_id = None

    def get_websocket_header(self, api_key):
        ua = 'dashscope/%s; python/%s; platform/%s; processor/%s' % (
            '1.18.0',  # dashscope version
            platform.python_version(),
            platform.platform(),
            platform.processor(),
        )
        self.ws_headers = {
            "User-Agent": ua,
            "Authorization": f"bearer {api_key}",
            "Accept": "application/json"
        }
        logger.info('websocket header: {}'.format(self.ws_headers))
        return self.ws_headers

    def generate_start_request(self, direction_name: str,
                               dialog_id: str,
                               app_id: str,
                               request_params: RequestParameters,
                               model: str = None,
                               workspace_id: str = None
                               ) -> str:
        """
        构建语音聊天服务的启动请求数据.
        :param app_id: 管控台应用id
        :param request_params: start请求body中的parameters
        :param direction_name:
        :param dialog_id: 对话ID.
        :param workspace_id: 管控台工作空间id, 非必填字段。
        :param model: 模型
        :return: 启动请求字典.
        """
        self._get_dash_request_header(ActionType.START)
        self._get_dash_request_payload(direction_name, dialog_id, app_id, workspace_id=workspace_id,
                                       request_params=request_params, model=model)

        cmd = {
            "header": self.header,
            "payload": self.payload
        }
        return json.dumps(cmd)

    def generate_common_direction_request(self, direction_name: str, dialog_id: str) -> str:
        """
        构建语音聊天服务的命令请求数据.
        :param direction_name: 命令.
        :param dialog_id: 对话ID.
        :return: 命令请求json.
        """
        self._get_dash_request_header(ActionType.CONTINUE)
        self._get_dash_request_payload(direction_name, dialog_id, self.app_id)
        cmd = {
            "header": self.header,
            "payload": self.payload
        }
        return json.dumps(cmd)

    def generate_stop_request(self, direction_name: str, dialog_id: str) -> str:
        """
        构建语音聊天服务的启动请求数据.
        :param direction_name:指令名称
        :param dialog_id: 对话ID.
        :return: 启动请求json.
        """
        self._get_dash_request_header(ActionType.FINISHED)
        self._get_dash_request_payload(direction_name, dialog_id, self.app_id)

        cmd = {
            "header": self.header,
            "payload": self.payload
        }
        return json.dumps(cmd)

    def generate_request_to_response_json(self, direction_name: str, dialog_id: str, request_type: str, text: str,
                                          parameters: RequestToRespondParameters = None) -> str:
        """
        构建语音聊天服务的命令请求数据.
        :param direction_name: 命令.
        :param dialog_id: 对话ID.
        :param request_type: 服务应该采取的交互类型，transcript 表示直接把文本转语音，prompt 表示把文本送大模型回答
        :param text: 文本.
        :param parameters: 命令请求body中的parameters
        :return: 命令请求字典.
        """
        self._get_dash_request_header(ActionType.CONTINUE)

        custom_input = RequestToRespondBodyInput(
            app_id=self.app_id,
            directive=direction_name,
            dialog_id=dialog_id,
            type_=request_type,
            text=text
        )

        self._get_dash_request_payload(direction_name, dialog_id, self.app_id, request_params=parameters,
                                       custom_input=custom_input)
        cmd = {
            "header": self.header,
            "payload": self.payload
        }
        return json.dumps(cmd)

    def generate_update_info_json(self, direction_name: str, dialog_id: str,parameters: RequestToRespondParameters = None) -> str:
        """
        构建语音聊天服务的命令请求数据.
        :param direction_name: 命令.
        :param parameters: 命令请求body中的parameters
        :return: 命令请求字典.
        """
        self._get_dash_request_header(ActionType.CONTINUE)

        custom_input = RequestToRespondBodyInput(
            app_id=self.app_id,
            directive=direction_name,
            dialog_id=dialog_id,
        )

        self._get_dash_request_payload(direction_name, dialog_id, self.app_id, request_params=parameters,
                                       custom_input=custom_input)
        cmd = {
            "header": self.header,
            "payload": self.payload
        }
        return json.dumps(cmd)

    def _get_dash_request_header(self, action: str):
        """
        构建多模对话请求的请求协议Header
        :param action: ActionType 百炼协议action 支持：run-task, continue-task, finish-task
        """
        if self.task_id is None:
            self.task_id = get_random_uuid()
        self.header = DashHeader(action=action, task_id=self.task_id).to_dict()

    def _get_dash_request_payload(self, direction_name: str,
                                  dialog_id: str, app_id: str, workspace_id: str = None,
                                  request_params: RequestParameters = None, custom_input=None, model: str = None):
        """
        构建多模对话请求的请求协议payload
        :param direction_name: 对话协议内部的指令名称
        :param dialog_id: 对话ID.
        :param app_id: 管控台应用id
        :param request_params: start请求body中的parameters
        :param custom_input: 自定义输入
        :param model: 模型
        """
        if custom_input is not None:
            input = custom_input
        else:
            input = RequestBodyInput(
                workspace_id=workspace_id,
                app_id=app_id,
                directive=direction_name,
                dialog_id=dialog_id
            )

        self.payload = DashPayload(
            model=model,
            input=input,
            parameters=request_params
        ).to_dict()


class _Response:
    def __init__(self, state: dialog_state.StateMachine, callback: MultiModalCallback, close_callback=None):
        super().__init__()
        self.dialog_id = None  # 对话ID.
        self.dialog_state = state
        self._callback = callback
        self._close_callback = close_callback  # 保存关闭回调函数

    def handle_text_response(self, response_json: str):
        """
        处理语音聊天服务的响应数据.
        :param response_json: 从服务接收到的原始JSON字符串响应。
        """
        logger.info("<<<<<< server response: %s" % response_json)
        try:
            # 尝试将消息解析为JSON
            json_data = json.loads(response_json)
            if "status_code" in json_data["header"] and json_data["header"]["status_code"] != 200:
                logger.error("Server returned invalid message: %s" % response_json)
                if self._callback:
                    self._callback.on_error(response_json)
                return
            if "event" in json_data["header"] and json_data["header"]["event"] == "task-failed":
                logger.error("Server returned invalid message: %s" % response_json)
                if self._callback:
                    self._callback.on_error(response_json)
                return None

            payload = json_data["payload"]
            if "output" in payload and payload["output"] is not None:
                response_event = payload["output"]["event"]
                logger.info("Server response event: %s" % response_event)
                self._handle_text_response_in_conversation(response_event=response_event, response_json=json_data)
            del json_data

        except json.JSONDecodeError:
            logger.error("Failed to parse message as JSON.")

    def _handle_text_response_in_conversation(self, response_event: str, response_json: dict):
        payload = response_json["payload"]
        try:
            if response_event == RESPONSE_NAME_STARTED:
                self._handle_started(payload["output"])
            elif response_event == RESPONSE_NAME_STOPPED:
                self._handle_stopped()
            elif response_event == RESPONSE_NAME_STATE_CHANGED:
                self._handle_state_changed(payload["output"]["state"])
                logger.debug("service response change state: %s" % payload["output"]["state"])
            elif response_event == RESPONSE_NAME_REQUEST_ACCEPTED:
                self._handle_request_accepted()
            elif response_event == RESPONSE_NAME_SPEECH_STARTED:
                self._handle_speech_started()
            elif response_event == RESPONSE_NAME_SPEECH_ENDED:
                self._handle_speech_ended()
            elif response_event == RESPONSE_NAME_RESPONDING_STARTED:
                self._handle_responding_started()
            elif response_event == RESPONSE_NAME_RESPONDING_ENDED:
                self._handle_responding_ended(payload)
            elif response_event == RESPONSE_NAME_SPEECH_CONTENT:
                self._handle_speech_content(payload)
            elif response_event == RESPONSE_NAME_RESPONDING_CONTENT:
                self._handle_responding_content(payload)
            elif response_event == RESPONSE_NAME_ERROR:
                self._callback.on_error(json.dumps(response_json))
            elif response_event == RESPONSE_NAME_HEART_BEAT:
                logger.debug("Server response heart beat")
            else:
                logger.error("Unknown response name: {}", response_event)
        except json.JSONDecodeError:
            logger.error("Failed to parse message as JSON.")

    def handle_binary_response(self, message: bytes):
        # logger.debug('<<<recv binary {}'.format(len(message)))
        self._callback.on_speech_audio_data(message)

    def _handle_request_accepted(self):
        self._callback.on_request_accepted()

    def _handle_started(self, payload: dict):
        self.dialog_id = payload["dialog_id"]
        self._callback.on_started(self.dialog_id)

    def _handle_stopped(self):
        self._callback.on_stopped()
        if self._close_callback is not None:
            self._close_callback()

    def _handle_state_changed(self, state: str):
        """
        处理语音聊天状态流转.
        :param state: 状态.
        """
        self.dialog_state.change_state(state)
        self._callback.on_state_changed(self.dialog_state.get_current_state())

    def _handle_speech_started(self):
        self._callback.on_speech_started()

    def _handle_speech_ended(self):
        self._callback.on_speech_ended()

    def _handle_responding_started(self):
        self._callback.on_responding_started()

    def _handle_responding_ended(self, payload: dict):
        self._callback.on_responding_ended(payload)

    def _handle_speech_content(self, payload: dict):
        self._callback.on_speech_content(payload)

    def _handle_responding_content(self, payload: dict):
        self._callback.on_responding_content(payload)
