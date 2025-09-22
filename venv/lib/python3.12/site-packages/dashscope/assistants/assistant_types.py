# Copyright (c) Alibaba, Inc. and its affiliates.

# adapter from openai sdk
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from dashscope.common.base_type import BaseList, BaseObjectMixin

__all__ = [
    'Assistant', 'AssistantFile', 'ToolCodeInterpreter', 'ToolSearch',
    'ToolWanX', 'FunctionDefinition', 'ToolFunction', 'AssistantFileList',
    'AssistantList', 'DeleteResponse'
]


@dataclass(init=False)
class AssistantFile(BaseObjectMixin):
    id: str
    assistant_id: str
    created_at: int
    object: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class ToolCodeInterpreter(BaseObjectMixin):
    type: str = 'code_interpreter'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class ToolSearch(BaseObjectMixin):
    type: str = 'search'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class ToolWanX(BaseObjectMixin):
    type: str = 'wanx'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class FunctionDefinition(BaseObjectMixin):
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, object]] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class ToolFunction(BaseObjectMixin):
    function: FunctionDefinition
    type: str = 'function'

    def __init__(self, **kwargs):
        self.function = FunctionDefinition(**kwargs.pop('function', {}))
        super().__init__(**kwargs)


Tool = Union[ToolCodeInterpreter, ToolSearch, ToolFunction, ToolWanX]
ASSISTANT_SUPPORT_TOOL = {
    'code_interpreter': ToolCodeInterpreter,
    'search': ToolSearch,
    'wanx': ToolWanX,
    'function': ToolFunction
}


def convert_tools_dict_to_objects(tools):
    tools_object = []
    for tool in tools:
        if 'type' in tool:
            tool_type = ASSISTANT_SUPPORT_TOOL.get(tool['type'], None)
            if tool_type:
                tools_object.append(tool_type(**tool))
            else:
                tools_object.append(tool)
        else:
            tools_object.append(tool)
    return tools_object


@dataclass(init=False)
class Assistant(BaseObjectMixin):
    status_code: int
    """The call response status_code, 200 indicate create success.
    """
    code: str
    """The request failed, this is the error code.
    """
    message: str
    """The request failed, this is the error message.
    """
    id: str
    """ID of the assistant.
    """
    model: str
    name: Optional[str] = None
    created_at: int
    """The Unix timestamp (in seconds) for when the assistant was created.
    """
    description: Optional[str] = None

    file_ids: List[str]

    instructions: Optional[str] = None
    metadata: Optional[object] = None
    tools: List[Tool]

    object: Optional[str] = None

    top_p: Optional[float] = None
    top_k: Optional[int] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    request_id: Optional[str] = None

    def __init__(self, **kwargs):
        self.tools = convert_tools_dict_to_objects(kwargs.pop('tools', []))
        super().__init__(**kwargs)


@dataclass(init=False)
class AssistantList(BaseList):
    data: List[Assistant]

    def __init__(self,
                 has_more: bool = None,
                 last_id: Optional[str] = None,
                 first_id: Optional[str] = None,
                 data: List[Assistant] = [],
                 **kwargs):
        super().__init__(has_more=has_more,
                         last_id=last_id,
                         first_id=first_id,
                         data=data,
                         **kwargs)


@dataclass(init=False)
class AssistantFileList(BaseList):
    data: List[AssistantFile]

    def __init__(self,
                 has_more: bool = None,
                 last_id: Optional[str] = None,
                 first_id: Optional[str] = None,
                 data: List[AssistantFile] = [],
                 **kwargs):
        super().__init__(has_more=has_more,
                         last_id=last_id,
                         first_id=first_id,
                         data=data,
                         **kwargs)


@dataclass(init=False)
class DeleteResponse(BaseObjectMixin):
    id: str
    deleted: bool

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
