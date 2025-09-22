from dataclasses import dataclass, field, asdict
import uuid


def get_random_uuid() -> str:
    """生成并返回32位UUID字符串"""
    return uuid.uuid4().hex


@dataclass
class DashHeader:
    action: str
    task_id: str = field(default=get_random_uuid())
    streaming: str = field(default="duplex")  # 默认为 duplex

    def to_dict(self):
        return {
            "action": self.action,
            "task_id": self.task_id,
            "request_id": self.task_id,
            "streaming": self.streaming
        }


class DashPayloadParameters:
    def to_dict(self):
        pass


class DashPayloadInput:
    def to_dict(self):
        pass


@dataclass
class DashPayload:
    task_group: str = field(default="aigc")
    function: str = field(default="generation")
    model: str = field(default="")
    task: str = field(default="multimodal-generation")
    parameters: DashPayloadParameters = field(default=None)
    input: DashPayloadInput = field(default=None)

    def to_dict(self):
        payload = {
            "task_group": self.task_group,
            "function": self.function,
            "model": self.model,
            "task": self.task,
        }

        if self.parameters is not None:
            payload["parameters"] = self.parameters.to_dict()

        if self.input is not None:
            payload["input"] = self.input.to_dict()

        return payload


@dataclass
class RequestBodyInput(DashPayloadInput):
    workspace_id: str
    app_id: str
    directive: str
    dialog_id: str

    def to_dict(self):
        return {
            "workspace_id": self.workspace_id,
            "app_id": self.app_id,
            "directive": self.directive,
            "dialog_id": self.dialog_id
        }


@dataclass
class Upstream:
    """struct for upstream"""
    audio_format: str = field(default="pcm")  # 上行语音格式，默认pcm.支持pcm/opus
    type: str = field(default="AudioOnly")  # 上行类型：AudioOnly 仅语音通话; AudioAndVideo 上传视频
    mode: str = field(default="tap2talk")  # 客户端交互模式 push2talk/tap2talk/duplex
    # sample_rate: int  # 合成音频采样率
    pass_through_params: dict = field(default=None)

    def to_dict(self):
        upstream: dict = {
            "type": self.type,
            "mode": self.mode,
            "audio_format": self.audio_format,
            # "sample_rate": self.sample_rate
        }
        if self.pass_through_params is not None:
            upstream.update(self.pass_through_params)
        return upstream


@dataclass
class Downstream:
    # transcript  返回用户语音识别结果
    # dialog 返回对话系统回答中间结果
    # 可以设置多种，以逗号分割，默认为transcript
    voice: str = field(default="")  # 语音音色
    sample_rate: int = field(default=0)  # 语音音色 # 合成音频采样率
    intermediate_text: str = field(default="transcript")  # 控制返回给用户那些中间文本：
    debug: bool = field(default=False)  # 控制是否返回debug信息
    # type_: str = field(default="Audio", metadata={"alias": "type"})  # 下行类型：Text：不需要下发语音;Audio：输出语音，默认值
    audio_format: str = field(default="pcm")  # 下行语音格式，默认pcm 。支持pcm/mp3
    volume: int = field(default=50)  # 语音音量 0-100
    pitch_rate: int = field(default=100)  # 语音语调 50-200
    speech_rate: int = field(default=100)  # 语音语速 50-200
    pass_through_params: dict = field(default=None)

    def to_dict(self):
        stream: dict = {
            "intermediate_text": self.intermediate_text,
            "debug": self.debug,
            # "type": self.type_,
            "audio_format": self.audio_format,
            "volume": self.volume,
            "pitch_rate": self.pitch_rate,
            "speech_rate": self.speech_rate
        }
        if self.voice != "":
            stream["voice"] = self.voice
        if self.sample_rate != 0:
            stream["sample_rate"] = self.sample_rate
        if self.pass_through_params is not None:
            stream.update(self.pass_through_params)
        return stream


@dataclass
class DialogAttributes:
    agent_id: str = field(default=None)
    prompt: str = field(default=None)
    vocabulary_id: str = field(default=None)

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "prompt": self.prompt,
            "vocabulary_id": self.vocabulary_id
        }


@dataclass
class Locations:
    city_name: str = field(default=None)
    latitude: str = field(default=None)
    longitude: str = field(default=None)

    def to_dict(self):
        return {
            "city_name": self.city_name,
            "latitude": self.latitude,
            "longitude": self.longitude
        }


@dataclass
class Network:
    ip: str = field(default=None)

    def to_dict(self):
        return {
            "ip": self.ip
        }


@dataclass
class Device:
    uuid: str = field(default=None)

    def to_dict(self):
        return {
            "uuid": self.uuid
        }


@dataclass
class ClientInfo:
    user_id: str
    device: Device = field(default=None)
    network: Network = field(default=None)
    location: Locations = field(default=None)

    def to_dict(self):
        info = {
            "user_id": self.user_id
        }
        if self.device is not None:
            info["device"] = self.device.to_dict()
        if self.network is not None:
            info["network"] = self.network.to_dict()
        if self.location is not None:
            info["location"] = self.location.to_dict()
        return info


@dataclass
class BizParams:
    user_defined_params: dict = field(default=None)
    user_defined_tokens: dict = field(default=None)
    tool_prompts: dict = field(default=None)
    user_prompt_params: dict = field(default=None)
    user_query_params: dict = field(default=None)
    videos: list = field(default=None)
    pass_through_params: dict = field(default=None)

    def to_dict(self):
        params = {}
        if self.user_defined_params is not None:
            params["user_defined_params"] = self.user_defined_params
        if self.user_defined_tokens is not None:
            params["user_defined_tokens"] = self.user_defined_tokens
        if self.tool_prompts is not None:
            params["tool_prompts"] = self.tool_prompts
        if self.user_prompt_params is not None:
            params["user_prompt_params"] = self.user_prompt_params
        if self.user_query_params is not None:
            params["user_query_params"] = self.user_query_params
        if self.videos is not None:
            params["videos"] = self.videos
        if self.pass_through_params is not None:
            params.update(self.pass_through_params)
        return params


@dataclass
class RequestParameters(DashPayloadParameters):
    upstream: Upstream
    downstream: Downstream
    client_info: ClientInfo
    dialog_attributes: DialogAttributes = field(default=None)
    biz_params: BizParams = field(default=None)

    def to_dict(self):
        params = {
            "upstream": self.upstream.to_dict(),
            "downstream": self.downstream.to_dict(),
            "client_info": self.client_info.to_dict(),
        }

        if self.dialog_attributes is not None:
            params["dialog_attributes"] = self.dialog_attributes.to_dict()
        if self.biz_params is not None:
            params["biz_params"] = self.biz_params.to_dict()
        return params


@dataclass
class RequestToRespondParameters(DashPayloadParameters):
    images: list = field(default=None)
    biz_params: BizParams = field(default=None)

    def to_dict(self):
        params = {
        }
        if self.images is not None:
            params["images"] = self.images
        if self.biz_params is not None:
            params["biz_params"] = self.biz_params.to_dict()
        return params


@dataclass
class RequestToRespondBodyInput(DashPayloadInput):
    app_id: str
    directive: str
    dialog_id: str
    type_: str = field(metadata={"alias": "type"}, default= None)
    text: str = field(default="")

    def to_dict(self):
        return {
            "app_id": self.app_id,
            "directive": self.directive,
            "dialog_id": self.dialog_id,
            "type": self.type_,
            "text": self.text
        }