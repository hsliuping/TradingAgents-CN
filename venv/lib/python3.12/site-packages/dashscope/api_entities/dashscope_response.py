# Copyright (c) Alibaba, Inc. and its affiliates.

import json
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Dict, List, Union


@dataclass(init=False)
class DictMixin(dict):
    __slots__ = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        return super().__getitem__(key)

    def __copy__(self):
        return type(self)(**self)

    def __deepcopy__(self, memo):
        id_self = id(self)
        _copy = memo.get(id_self)
        if _copy is None:
            _copy = type(self)(**self)
            memo[id_self] = _copy
        return _copy

    def __setitem__(self, key, value):
        return super().__setitem__(key, value)

    def __delitem__(self, key):
        return super().__delitem__(key)

    def get(self, key, default=None):
        return super().get(key, default)

    def setdefault(self, key, default=None):
        return super().setdefault(key, default)

    def pop(self, key, default: Any):
        return super().pop(key, default)

    def update(self, **kwargs):
        super().update(**kwargs)

    def __contains__(self, key):
        return super().__contains__(key)

    def copy(self):
        return type(self)(self)

    def getattr(self, attr):
        return super().get(attr)

    def setattr(self, attr, value):
        return super().__setitem__(attr, value)

    def __getattr__(self, attr):
        return self[attr]

    def __setattr__(self, attr, value):
        self[attr] = value

    def __repr__(self):
        return '{0}({1})'.format(type(self).__name__, super().__repr__())

    def __str__(self):
        return json.dumps(self, ensure_ascii=False)


@dataclass(init=False)
class DashScopeAPIResponse(DictMixin):
    """The response content

    Args:
        request_id (str): The request id.
        status_code (int): HTTP status code, 200 indicates that the
            request was successful, and others indicate an error。
        code (str): Error code if error occurs, otherwise empty str.
        message (str): Set to error message on error.
        output (Any): The request output.
        usage (Any): The request usage information.
    """
    status_code: int
    request_id: str
    code: str
    message: str
    output: Any
    usage: Any

    def __init__(self,
                 status_code: int,
                 request_id: str = '',
                 code: str = '',
                 message: str = '',
                 output: Any = None,
                 usage: Any = None,
                 **kwargs):
        super().__init__(status_code=status_code,
                         request_id=request_id,
                         code=code,
                         message=message,
                         output=output,
                         usage=usage,
                         **kwargs)


class Role:
    USER = 'user'
    SYSTEM = 'system'
    BOT = 'bot'
    ASSISTANT = 'assistant'
    ATTACHMENT = 'attachment'


class Message(DictMixin):
    role: str
    content: Union[str, List]

    def __init__(self, role: str, content: str = None, **kwargs):
        super().__init__(role=role, content=content, **kwargs)

    @classmethod
    def from_generation_response(cls, response: DictMixin):
        if 'text' in response.output and response.output['text'] is not None:
            content = response.output['text']
            return Message(role=Role.ASSISTANT, content=content)
        else:
            return response.output.choices[0]['message']

    @classmethod
    def from_conversation_response(cls, response: DictMixin):
        return cls.from_generation_response(response)


@dataclass(init=False)
class Choice(DictMixin):
    finish_reason: str
    message: Message

    def __init__(self,
                 finish_reason: str = None,
                 message: Message = None,
                 **kwargs):
        msgObject = None
        if message is not None and message:
            msgObject = Message(**message)
        super().__init__(finish_reason=finish_reason,
                         message=msgObject,
                         **kwargs)


@dataclass(init=False)
class GenerationOutput(DictMixin):
    text: str
    choices: List[Choice]
    finish_reason: str

    def __init__(self,
                 text: str = None,
                 finish_reason: str = None,
                 choices: List[Choice] = None,
                 **kwargs):
        chs = None
        if choices is not None:
            chs = []
            for choice in choices:
                chs.append(Choice(**choice))
        super().__init__(text=text,
                         finish_reason=finish_reason,
                         choices=chs,
                         **kwargs)


@dataclass(init=False)
class GenerationUsage(DictMixin):
    input_tokens: int
    output_tokens: int

    def __init__(self,
                 input_tokens: int = 0,
                 output_tokens: int = 0,
                 **kwargs):
        super().__init__(input_tokens=input_tokens,
                         output_tokens=output_tokens,
                         **kwargs)


@dataclass(init=False)
class GenerationResponse(DashScopeAPIResponse):
    output: GenerationOutput
    usage: GenerationUsage

    @staticmethod
    def from_api_response(api_response: DashScopeAPIResponse):
        if api_response.status_code == HTTPStatus.OK:
            usage = {}
            if api_response.usage:
                usage = api_response.usage

            return GenerationResponse(
                status_code=api_response.status_code,
                request_id=api_response.request_id,
                code=api_response.code,
                message=api_response.message,
                output=GenerationOutput(**api_response.output),
                usage=GenerationUsage(**usage))
        else:
            return GenerationResponse(status_code=api_response.status_code,
                                      request_id=api_response.request_id,
                                      code=api_response.code,
                                      message=api_response.message)


@dataclass(init=False)
class MultiModalConversationOutput(DictMixin):
    choices: List[Choice]

    def __init__(self,
                 text: str = None,
                 finish_reason: str = None,
                 choices: List[Choice] = None,
                 **kwargs):
        chs = None
        if choices is not None:
            chs = []
            for choice in choices:
                chs.append(Choice(**choice))
        super().__init__(text=text,
                         finish_reason=finish_reason,
                         choices=chs,
                         **kwargs)


@dataclass(init=False)
class MultiModalConversationUsage(DictMixin):
    input_tokens: int
    output_tokens: int

    # TODO add image usage info.

    def __init__(self,
                 input_tokens: int = 0,
                 output_tokens: int = 0,
                 **kwargs):
        super().__init__(input_tokens=input_tokens,
                         output_tokens=output_tokens,
                         **kwargs)


@dataclass(init=False)
class MultiModalConversationResponse(DashScopeAPIResponse):
    output: MultiModalConversationOutput
    usage: MultiModalConversationUsage

    @staticmethod
    def from_api_response(api_response: DashScopeAPIResponse):
        if api_response.status_code == HTTPStatus.OK:
            usage = {}
            if api_response.usage:
                usage = api_response.usage

            return MultiModalConversationResponse(
                status_code=api_response.status_code,
                request_id=api_response.request_id,
                code=api_response.code,
                message=api_response.message,
                output=MultiModalConversationOutput(**api_response.output),
                usage=MultiModalConversationUsage(**usage))
        else:
            return MultiModalConversationResponse(
                status_code=api_response.status_code,
                request_id=api_response.request_id,
                code=api_response.code,
                message=api_response.message)


@dataclass(init=False)
class ConversationResponse(GenerationResponse):
    pass


@dataclass(init=False)
class TranscriptionOutput(DictMixin):
    task_id: str
    task_status: str

    def __init__(self, task_id: str, task_status: str, **kwargs):
        super().__init__(task_id=task_id, task_status=task_status, **kwargs)


@dataclass(init=False)
class TranscriptionUsage(DictMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class TranscriptionResponse(DashScopeAPIResponse):
    output: TranscriptionOutput
    usage: TranscriptionUsage

    @staticmethod
    def from_api_response(api_response: DashScopeAPIResponse):
        if api_response.status_code == HTTPStatus.OK:
            output = None
            usage = None
            if api_response.output is not None:
                output = TranscriptionOutput(**api_response.output)
            if api_response.usage is not None:
                usage = TranscriptionUsage(**api_response.usage)

            return TranscriptionResponse(status_code=api_response.status_code,
                                         request_id=api_response.request_id,
                                         code=api_response.code,
                                         message=api_response.message,
                                         output=output,
                                         usage=usage)

        else:
            return TranscriptionResponse(status_code=api_response.status_code,
                                         request_id=api_response.request_id,
                                         code=api_response.code,
                                         message=api_response.message)


@dataclass(init=False)
class RecognitionOutput(DictMixin):
    sentence: Union[Dict[str, Any], List[Any]]

    def __init__(self, sentence: Union[Dict[str, Any], List[Any]], **kwargs):
        super().__init__(sentence=sentence, **kwargs)


@dataclass(init=False)
class RecognitionUsage(DictMixin):
    duration: int

    def __init__(self, duration: int = 0, **kwargs):
        super().__init__(duration=duration, **kwargs)


@dataclass(init=False)
class RecognitionResponse(DashScopeAPIResponse):
    output: RecognitionOutput
    usage: RecognitionUsage

    @staticmethod
    def from_api_response(api_response: DashScopeAPIResponse):
        if api_response.status_code == HTTPStatus.OK:
            output = None
            usage = None
            if api_response.output is not None:
                if 'sentence' in api_response.output:
                    output = RecognitionOutput(**api_response.output)
            if api_response.usage is not None:
                usage = RecognitionUsage(**api_response.usage)

            return RecognitionResponse(status_code=api_response.status_code,
                                       request_id=api_response.request_id,
                                       code=api_response.code,
                                       message=api_response.message,
                                       output=output,
                                       usage=usage)

        else:
            return RecognitionResponse(status_code=api_response.status_code,
                                       request_id=api_response.request_id,
                                       code=api_response.code,
                                       message=api_response.message)

    @staticmethod
    def is_sentence_end(sentence: Dict[str, Any]) -> bool:
        """Determine whether the speech recognition result is the end of a sentence.
           This is a static method.
        """
        result = False
        if sentence is not None and 'end_time' in sentence and sentence[
                'end_time'] is not None:
            result = True
        return result


@dataclass(init=False)
class SpeechSynthesisOutput(DictMixin):
    sentence: Dict[str, Any]

    def __init__(self, sentence: Dict[str, Any], **kwargs):
        super().__init__(sentence=sentence, **kwargs)


@dataclass(init=False)
class SpeechSynthesisUsage(DictMixin):
    characters: int

    def __init__(self, characters: int = 0, **kwargs):
        super().__init__(characters=characters, **kwargs)


@dataclass(init=False)
class SpeechSynthesisResponse(DashScopeAPIResponse):
    output: SpeechSynthesisOutput
    usage: SpeechSynthesisUsage

    @staticmethod
    def from_api_response(api_response: DashScopeAPIResponse):
        if api_response.status_code == HTTPStatus.OK:
            output = None
            usage = None
            if api_response.output is not None:
                output = SpeechSynthesisOutput(**api_response.output)
            if api_response.usage is not None:
                usage = SpeechSynthesisUsage(**api_response.usage)

            return SpeechSynthesisResponse(
                status_code=api_response.status_code,
                request_id=api_response.request_id,
                code=api_response.code,
                message=api_response.message,
                output=output,
                usage=usage)

        else:
            return SpeechSynthesisResponse(
                status_code=api_response.status_code,
                request_id=api_response.request_id,
                code=api_response.code,
                message=api_response.message)


@dataclass(init=False)
class ImageSynthesisResult(DictMixin):
    url: str

    def __init__(self, url: str = '', **kwargs) -> None:
        super().__init__(url=url, **kwargs)


@dataclass(init=False)
class ImageSynthesisOutput(DictMixin):
    task_id: str
    task_status: str
    results: List[ImageSynthesisResult]

    def __init__(self,
                 task_id: str,
                 task_status: str,
                 results: List[ImageSynthesisResult] = [],
                 **kwargs):
        res = []
        if len(results) > 0:
            for result in results:
                res.append(ImageSynthesisResult(**result))
        super().__init__(self,
                         task_id=task_id,
                         task_status=task_status,
                         results=res,
                         **kwargs)


@dataclass(init=False)
class VideoSynthesisOutput(DictMixin):
    task_id: str
    task_status: str
    video_url: str

    def __init__(self,
                 task_id: str,
                 task_status: str,
                 video_url: str = '',
                 **kwargs):
        super().__init__(self,
                         task_id=task_id,
                         task_status=task_status,
                         video_url=video_url,
                         **kwargs)


@dataclass(init=False)
class ImageSynthesisUsage(DictMixin):
    image_count: int

    def __init__(self, image_count: int = None, **kwargs):
        super().__init__(image_count=image_count, **kwargs)


@dataclass(init=False)
class VideoSynthesisUsage(DictMixin):
    video_count: int
    video_duration: int
    video_ratio: str

    def __init__(self,
                 video_count: int = 1,
                 video_duration: int = 0,
                 video_ratio: str = '',
                 **kwargs):
        super().__init__(video_count=video_count,
                         video_duration=video_duration,
                         video_ratio=video_ratio,
                         **kwargs)


@dataclass(init=False)
class ImageSynthesisResponse(DashScopeAPIResponse):
    output: ImageSynthesisOutput
    usage: ImageSynthesisUsage

    @staticmethod
    def from_api_response(api_response: DashScopeAPIResponse):
        if api_response.status_code == HTTPStatus.OK:
            output = None
            usage = None
            if api_response.output is not None:
                output = ImageSynthesisOutput(**api_response.output)
            if api_response.usage is not None:
                usage = ImageSynthesisUsage(**api_response.usage)

            return ImageSynthesisResponse(status_code=api_response.status_code,
                                          request_id=api_response.request_id,
                                          code=api_response.code,
                                          message=api_response.message,
                                          output=output,
                                          usage=usage)

        else:
            return ImageSynthesisResponse(status_code=api_response.status_code,
                                          request_id=api_response.request_id,
                                          code=api_response.code,
                                          message=api_response.message)


@dataclass(init=False)
class VideoSynthesisResponse(DashScopeAPIResponse):
    output: VideoSynthesisOutput
    usage: VideoSynthesisUsage

    @staticmethod
    def from_api_response(api_response: DashScopeAPIResponse):
        if api_response.status_code == HTTPStatus.OK:
            output = None
            usage = None
            if api_response.output is not None:
                output = VideoSynthesisOutput(**api_response.output)
            if api_response.usage is not None:
                usage = VideoSynthesisUsage(**api_response.usage)

            return VideoSynthesisResponse(status_code=api_response.status_code,
                                          request_id=api_response.request_id,
                                          code=api_response.code,
                                          message=api_response.message,
                                          output=output,
                                          usage=usage)

        else:
            return VideoSynthesisResponse(status_code=api_response.status_code,
                                          request_id=api_response.request_id,
                                          code=api_response.code,
                                          message=api_response.message)


@dataclass(init=False)
class ReRankResult(DictMixin):
    index: int
    relevance_score: float
    document: Dict = None

    def __init__(self,
                 index: int,
                 relevance_score: float,
                 document: Dict = None,
                 **kwargs):
        super().__init__(index=index,
                         relevance_score=relevance_score,
                         document=document,
                         **kwargs)


@dataclass(init=False)
class ReRankOutput(DictMixin):
    results: List[ReRankResult]

    def __init__(self, results: List[ReRankResult] = None, **kwargs):
        ress = None
        if results is not None:
            ress = []
            for res in results:
                ress.append(ReRankResult(**res))
        super().__init__(results=ress, **kwargs)


@dataclass(init=False)
class ReRankUsage(DictMixin):
    total_tokens: int

    def __init__(self, total_tokens=None, **kwargs):
        super().__init__(total_tokens=total_tokens, **kwargs)


@dataclass(init=False)
class ReRankResponse(DashScopeAPIResponse):
    output: ReRankOutput
    usage: GenerationUsage

    @staticmethod
    def from_api_response(api_response: DashScopeAPIResponse):
        if api_response.status_code == HTTPStatus.OK:
            usage = {}
            if api_response.usage:
                usage = api_response.usage

            return ReRankResponse(status_code=api_response.status_code,
                                  request_id=api_response.request_id,
                                  code=api_response.code,
                                  message=api_response.message,
                                  output=ReRankOutput(**api_response.output),
                                  usage=ReRankUsage(**usage))
        else:
            return ReRankResponse(status_code=api_response.status_code,
                                  request_id=api_response.request_id,
                                  code=api_response.code,
                                  message=api_response.message)


@dataclass(init=False)
class TextToSpeechAudio(DictMixin):
    expires_at: int
    id: str
    data: str
    url: str

    def __init__(self,
                 expires_at: int,
                 id: str,
                 data: str = None,
                 url: str = None,
                 **kwargs):
        super().__init__(expires_at=expires_at,
                         id=id,
                         data=data,
                         url=url,
                         **kwargs)


@dataclass(init=False)
class TextToSpeechOutput(DictMixin):
    finish_reason: str
    audio: TextToSpeechAudio

    def __init__(self,
                 finish_reason: str = None,
                 audio: TextToSpeechAudio = None,
                 **kwargs):
        super().__init__(finish_reason=finish_reason,
                         audio=audio,
                         **kwargs)


@dataclass(init=False)
class TextToSpeechResponse(DashScopeAPIResponse):
    output: TextToSpeechOutput
    usage: MultiModalConversationUsage

    @staticmethod
    def from_api_response(api_response: DashScopeAPIResponse):
        if api_response.status_code == HTTPStatus.OK:
            usage = {}
            if api_response.usage:
                usage = api_response.usage

            return MultiModalConversationResponse(
                status_code=api_response.status_code,
                request_id=api_response.request_id,
                code=api_response.code,
                message=api_response.message,
                output=TextToSpeechOutput(**api_response.output),
                usage=MultiModalConversationUsage(**usage))
        else:
            return TextToSpeechResponse(
                status_code=api_response.status_code,
                request_id=api_response.request_id,
                code=api_response.code,
                message=api_response.message)
