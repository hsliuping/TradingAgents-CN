# Copyright (c) Alibaba, Inc. and its affiliates.

# adapter from openai sdk
# yapf: disable
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Union

from dashscope.assistants.assistant_types import (
    Tool, convert_tools_dict_to_objects)
from dashscope.common.base_type import BaseList, BaseObjectMixin

__all__ = [
    'MessageFile', 'MessageFileList', 'Usage', 'ImageFile',
    'MessageContentImageFile', 'Text', 'MessageContentText', 'ThreadMessage',
    'ThreadMessageList', 'Thread', 'Function',
    'RequiredActionFunctionToolCall', 'RequiredActionSubmitToolOutputs',
    'RequiredAction', 'LastError', 'Run', 'RunList', 'MessageCreation',
    'MessageCreationStepDetails', 'CodeInterpreterOutputLogs',
    'CodeInterpreterOutputImageImage', 'CodeInterpreterOutputImage',
    'CodeInterpreter', 'CodeToolCall', 'RetrievalToolCall', 'FunctionToolCall',
    'ToolCallsStepDetails', 'RunStep', 'RunStepList'
]


@dataclass(init=False)
class MessageFile(BaseObjectMixin):
    id: str
    message_id: str
    created_at: int
    object: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class MessageFileList(BaseList):
    data: List[MessageFile]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class Usage(BaseObjectMixin):
    completion_tokens: int
    """Number of completion tokens used over the course of the run."""

    prompt_tokens: int
    """Number of prompt tokens used over the course of the run."""

    total_tokens: int
    """Total number of tokens used (prompt + completion)."""

    input_tokens: int
    """Input tokens used (prompt)."""

    output_tokens: int
    """Output tokens used (completion)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class ImageFile(BaseObjectMixin):
    file_id: str

    def __init__(self, file_id, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class MessageContentImageFile(BaseObjectMixin):
    type: str = 'image_file'
    image_file: ImageFile

    def __init__(self, **kwargs):
        self.image_file = ImageFile(**kwargs.pop(self.type, {}))
        super().__init__(**kwargs)


TextAnnotation = Union[Dict]


@dataclass(init=False)
class Text(BaseObjectMixin):
    annotations: List[TextAnnotation]
    value: str

    def __init__(self, **kwargs):
        annotations = kwargs.pop('annotations', None)
        if annotations:
            self.annotations = []
            for annotation in annotations:
                self.annotations.append(annotation)
        else:
            self.annotations = annotations
        super().__init__(**kwargs)


@dataclass(init=False)
class MessageContentText(BaseObjectMixin):
    text: Text
    type: str = 'text'

    def __init__(self, **kwargs):
        input_text = kwargs.pop('text', {})
        if input_text:
            self.text = Text(**input_text)
        super().__init__(**kwargs)


MESSAGE_SUPPORT_CONTENT = {
    'text': MessageContentText,
    'image_file': MessageContentImageFile,
}

Content = Union[MessageContentImageFile, MessageContentText]


@dataclass(init=False)
class ThreadMessageDeltaContent(BaseObjectMixin):
    content: Content
    role: str

    def __init__(self, **kwargs):
        contents = kwargs.pop('content', None)
        if contents:
            for item in contents:
                if item['type'] == 'text':
                    self.content = MessageContentText(**item)
                elif item['type'] == 'image_file':
                    self.content = MessageContentImageFile(**item)
                else:
                    self.content = item
        else:
            self.content = contents
        super().__init__(**kwargs)


@dataclass(init=False)
class ThreadMessageDelta(BaseObjectMixin):
    status_code: int
    id: str
    object: str = 'thread.message.delta'
    delta: ThreadMessageDeltaContent

    def __init__(self, **kwargs):
        content = kwargs.pop('delta', None)
        if content:
            self.delta = ThreadMessageDeltaContent(**content)
        else:
            self.delta = None
        super().__init__(**kwargs)


@dataclass(init=False)
class ThreadMessage(BaseObjectMixin):
    status_code: int
    id: str
    created_at: int
    thread_id: str
    role: str
    content: List[Content]
    metadata: Optional[object] = None
    object: str = 'thread.message'
    assistant_id: Optional[str] = None
    file_ids: List[str] = None
    run_id: Optional[str] = None

    def __init__(self, **kwargs):
        input_content = kwargs.pop('content', None)
        if input_content:
            content_list = []
            for content in input_content:
                if 'type' in content:
                    content_type = MESSAGE_SUPPORT_CONTENT.get(
                        content['type'], None)
                    if content_type:
                        content_list.append(content_type(**content))
                    else:
                        content_list.append(content)
                else:
                    content_list.append(content)
            self.content = content_list
        else:
            self.content = input_content

        super().__init__(**kwargs)


@dataclass(init=False)
class ThreadMessageList(BaseList):
    data: List[ThreadMessage]

    def __init__(self,
                 has_more: bool = None,
                 last_id: Optional[str] = None,
                 first_id: Optional[str] = None,
                 data: List[ThreadMessage] = [],
                 **kwargs):
        super().__init__(has_more=has_more,
                         last_id=last_id,
                         first_id=first_id,
                         data=data,
                         **kwargs)


@dataclass(init=False)
class Thread(BaseObjectMixin):
    status_code: int
    id: str
    created_at: int
    metadata: Optional[object] = None
    object: str = 'thread'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class Function(BaseObjectMixin):
    arguments: str
    name: str
    output: Optional[str] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class RequiredActionFunctionToolCall(BaseObjectMixin):
    id: str

    function: Function

    type: str = 'function'

    def __init__(self, **kwargs):
        self.function = Function(**kwargs.pop('function', {}))
        super().__init__(**kwargs)


@dataclass(init=False)
class RequiredActionSubmitToolOutputs(BaseObjectMixin):
    tool_calls: List[RequiredActionFunctionToolCall]

    def __init__(self, **kwargs):
        tcs = kwargs.pop('tool_calls', [])
        if tcs:
            self.tool_calls = []
            for tc in tcs:
                self.tool_calls.append(RequiredActionFunctionToolCall(**tc))
        else:
            self.tool_calls = tcs
        super().__init__(**kwargs)


@dataclass(init=False)
class RequiredAction(BaseObjectMixin):
    submit_tool_outputs: RequiredActionSubmitToolOutputs

    type: Literal['submit_tool_outputs']

    def __init__(self, **kwargs):
        self.submit_tool_outputs = RequiredActionSubmitToolOutputs(
            **kwargs.pop('submit_tool_outputs', {}))
        super().__init__(**kwargs)


@dataclass(init=False)
class LastError(BaseObjectMixin):
    code: Literal['server_error', 'rate_limit_exceeded']
    message: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class Run(BaseObjectMixin):
    status_code: int
    id: str
    assistant_id: str
    cancelled_at: Optional[int] = None
    completed_at: Optional[int] = None
    created_at: int = None
    expires_at: int = None
    failed_at: Optional[int] = None
    file_ids: List[str] = None

    instructions: str = None

    metadata: Optional[object] = None
    last_error: Optional[LastError] = None
    model: str = None

    object: str = 'thread.run'

    required_action: Optional[RequiredAction] = None

    started_at: Optional[int] = None

    status: Literal['queued', 'in_progress', 'requires_action', 'cancelling',
                    'cancelled', 'failed', 'completed', 'expired']

    thread_id: str

    tools: List[Tool]

    top_p: Optional[float] = None
    top_k: Optional[int] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    usage: Optional[Usage] = None

    def __init__(self, **kwargs):
        self.tools = convert_tools_dict_to_objects(kwargs.pop('tools', []))
        actions = kwargs.pop('required_action', None)
        if actions:
            self.required_action = RequiredAction(**actions)
        else:
            self.required_action = actions

        super().__init__(**kwargs)


@dataclass(init=False)
class RunList(BaseObjectMixin):
    data: List[Run]

    def __init__(self,
                 has_more: bool = None,
                 last_id: Optional[str] = None,
                 first_id: Optional[str] = None,
                 data: List[Run] = [],
                 **kwargs):
        super().__init__(has_more=has_more,
                         last_id=last_id,
                         first_id=first_id,
                         data=data,
                         **kwargs)


@dataclass(init=False)
class MessageCreation(BaseObjectMixin):
    message_id: str
    """The ID of the message that was created by this run step."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class MessageCreationStepDetails(BaseObjectMixin):
    message_creation: MessageCreation

    type: Literal['message_creation']
    """Always `message_creation`."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class CodeInterpreterOutputLogs(BaseObjectMixin):
    logs: str
    """The text output from the Code Interpreter tool call."""

    type: Literal['logs']
    """Always `logs`."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class CodeInterpreterOutputImageImage(BaseObjectMixin):
    file_id: str
    """
    The [file](https://platform.openai.com/docs/api-reference/files) ID of the
    image.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class CodeInterpreterOutputImage(BaseObjectMixin):
    image: CodeInterpreterOutputImageImage

    type: Literal['image']
    """Always `image`."""
    def __init__(self, **kwargs):
        self.image = CodeInterpreterOutputImageImage(**kwargs.pop('image', {}))
        super().__init__(**kwargs)


CodeInterpreterOutput = Union[CodeInterpreterOutputLogs,
                              CodeInterpreterOutputImage]


@dataclass(init=False)
class CodeInterpreter(BaseObjectMixin):
    input: str
    """The input to the Code Interpreter tool call."""

    outputs: List[CodeInterpreterOutput]
    """The outputs from the Code Interpreter tool call.

    Code Interpreter can output one or more items, including text (`logs`) or images
    (`image`). Each of these are represented by a different object type.
    """
    def __init__(self, **kwargs):
        self.outputs = []
        for output in kwargs.pop('outputs', []):
            self.outputs.append(CodeInterpreterOutput(**output))

        super().__init__(**kwargs)


@dataclass(init=False)
class CodeToolCall(BaseObjectMixin):
    id: str
    """The ID of the tool call."""

    code_interpreter: CodeInterpreter
    """The Code Interpreter tool call definition."""

    type: Literal['code_interpreter']
    """The type of tool call.

    This is always going to be `code_interpreter` for this type of tool call.
    """
    def __init__(self, **kwargs):
        self.code_interpreter = CodeInterpreter(
            **kwargs.pop('code_interpreter', {}))
        super().__init__(**kwargs)


@dataclass(init=False)
class RetrievalToolCall(BaseObjectMixin):
    id: str
    """The ID of the tool call object."""

    retrieval: object
    """For now, this is always going to be an empty object."""

    type: Literal['quark_search']
    """The type of tool call.

    This is always going to be `quark_search` for this type of tool call.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class FunctionToolCall(BaseObjectMixin):
    id: str
    """The ID of the tool call object."""

    function: Function
    """The definition of the function that was called."""

    type: Literal['function']
    """The type of tool call.

    This is always going to be `function` for this type of tool call.
    """
    def __init__(self, **kwargs):
        self.function = Function(**kwargs.pop('function', {}))
        super().__init__(**kwargs)


ToolCall = Union[CodeToolCall, RetrievalToolCall, FunctionToolCall]

TOOL_CALL_TYPES = {
    'function': FunctionToolCall,
    'code_interpreter': CodeToolCall,
    'retrieval': RetrievalToolCall,
}


def convert_tool_calls_dict_to_object(tool_calls):
    tool_calls_object = []
    for tool_call in tool_calls:
        if 'type' in tool_call:
            tool_call_type = TOOL_CALL_TYPES.get(tool_call['type'], None)
            if tool_call_type:
                tool_calls_object.append(tool_call_type(**tool_call))
            else:
                tool_calls_object.append(tool_call)
        else:
            tool_calls_object.append(tool_call)
    return tool_calls_object


@dataclass(init=False)
class ToolCallsStepDetails(BaseObjectMixin):
    tool_calls: List[ToolCall]
    """An array of tool calls the run step was involved in.

    These can be associated with one of three types of tools: `code_interpreter`,
    `retrieval`, or `function`.
    """

    type: Literal['tool_calls']
    """Always `tool_calls`."""
    def __init__(self, **kwargs):
        self.tool_calls = convert_tool_calls_dict_to_object(
            kwargs.pop('tool_calls', []))
        super().__init__(**kwargs)


StepDetails = Union[MessageCreationStepDetails, ToolCallsStepDetails]
STEP_TYPES = {
    'tool_calls': ToolCallsStepDetails,
    'message_creation': MessageCreationStepDetails,
}


def convert_step_details_dict_to_objects(step_details):
    if 'type' in step_details:
        tool_type = STEP_TYPES.get(step_details['type'], None)
        if tool_type:
            return tool_type(**step_details)
    return step_details


@dataclass(init=False)
class RunStepDeltaContent(BaseObjectMixin):
    step_details: StepDetails

    def __init__(self, **kwargs):
        self.step_details = convert_step_details_dict_to_objects(
            kwargs.pop('step_details', {}))
        super().__init__(**kwargs)


@dataclass(init=False)
class RunStepDelta(BaseObjectMixin):
    id: str
    object: str = 'thread.run.step.delta'
    delta: RunStepDeltaContent

    def __init__(self, **kwargs):
        delta = kwargs.pop('delta', None)
        if delta:
            self.delta = RunStepDeltaContent(**delta)
        else:
            self.delta = delta
        super().__init__(**kwargs)


@dataclass(init=False)
class RunStep(BaseObjectMixin):
    status_code: int = None
    id: str
    """The identifier of the run step, which can be referenced in API endpoints."""

    assistant_id: str
    """
    The ID of the
    [assistant](https://platform.openai.com/docs/api-reference/assistants)
    associated with the run step.
    """

    cancelled_at: Optional[int] = None
    """The Unix timestamp (in seconds) for when the run step was cancelled."""

    completed_at: Optional[int] = None
    """The Unix timestamp (in seconds) for when the run step completed."""

    created_at: int
    """The Unix timestamp (in seconds) for when the run step was created."""

    expired_at: Optional[int] = None
    """The Unix timestamp (in seconds) for when the run step expired.

    A step is considered expired if the parent run is expired.
    """

    failed_at: Optional[int] = None
    """The Unix timestamp (in seconds) for when the run step failed."""

    last_error: Optional[LastError] = None
    """The last error associated with this run step.

    Will be `null` if there are no errors.
    """

    metadata: Optional[object] = None
    """Set of 16 key-value pairs that can be attached to an object.

    This can be useful for storing additional information about the object in a
    structured format. Keys can be a maximum of 64 characters long and values can be
    a maxium of 512 characters long.
    """

    object: Literal['thread.run.step']
    """The object type, which is always `thread.run.step`."""

    run_id: str
    """
    The ID of the [run](https://platform.openai.com/docs/api-reference/runs) that
    this run step is a part of.
    """

    status: Literal['in_progress', 'cancelled', 'failed', 'completed',
                    'expired']
    """
    The status of the run step, which can be either `in_progress`, `cancelled`,
    `failed`, `completed`, or `expired`.
    """

    step_details: StepDetails
    """The details of the run step."""

    thread_id: str
    """
    The ID of the [thread](https://platform.openai.com/docs/api-reference/threads)
    that was run.
    """

    type: Literal['message_creation', 'tool_calls']
    """The type of run step, which can be either `message_creation` or `tool_calls`."""

    usage: Optional[Usage] = None

    def __init__(self, **kwargs):
        self.step_details = convert_step_details_dict_to_objects(
            kwargs.pop('step_details', {}))
        if 'usage' in kwargs and kwargs['usage'] is not None and kwargs['usage']:
            self.usage = Usage(**kwargs.pop('usage', {}))
        else:
            self.usage = None
        last_error = kwargs.pop('last_error', None)
        if last_error:
            self.last_error = LastError(**last_error)
        else:
            last_error = last_error
        super().__init__(**kwargs)


@dataclass(init=False)
class RunStepList(BaseList):
    data: List[RunStep]

    def __init__(self,
                 has_more: bool = None,
                 last_id: Optional[str] = None,
                 first_id: Optional[str] = None,
                 data: List[RunStep] = [],
                 **kwargs):
        if data:
            steps = []
            for step in data:
                steps.append(RunStep(**step))
            self.data = steps
        else:
            self.data = []
        super().__init__(has_more=has_more,
                         last_id=last_id,
                         first_id=first_id,
                         **kwargs)
