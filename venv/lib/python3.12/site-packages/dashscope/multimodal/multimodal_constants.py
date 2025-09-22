# Copyright (c) Alibaba, Inc. and its affiliates.
# -*- coding: utf-8 -*-

# multimodal conversation request directive

class RequestToRespondType:
    TRANSCRIPT = 'transcript'
    PROMPT = 'prompt'


# multimodal conversation response directive
RESPONSE_NAME_TASK_STARTED = "task-started"
RESPONSE_NAME_RESULT_GENERATED = "result-generated"
RESPONSE_NAME_TASK_FINISHED = "task-finished"

RESPONSE_NAME_TASK_FAILED = "TaskFailed"
RESPONSE_NAME_STARTED = "Started"
RESPONSE_NAME_STOPPED = "Stopped"
RESPONSE_NAME_STATE_CHANGED = "DialogStateChanged"
RESPONSE_NAME_REQUEST_ACCEPTED = "RequestAccepted"
RESPONSE_NAME_SPEECH_STARTED = "SpeechStarted"
RESPONSE_NAME_SPEECH_ENDED = "SpeechEnded"  # 服务端检测到asr语音尾点时下发此事件,可选事件
RESPONSE_NAME_RESPONDING_STARTED = "RespondingStarted"  # AI语音应答开始，sdk要准备接收服务端下发的语音数据
RESPONSE_NAME_RESPONDING_ENDED = "RespondingEnded"  # AI语音应答结束
RESPONSE_NAME_SPEECH_CONTENT = "SpeechContent"  # 用户语音识别出的文本，流式全量输出
RESPONSE_NAME_RESPONDING_CONTENT = "RespondingContent"  # 统对外输出的文本，流式全量输出
RESPONSE_NAME_ERROR = "Error"  # 服务端对话中报错
RESPONSE_NAME_HEART_BEAT = "HeartBeat"  # 心跳消息