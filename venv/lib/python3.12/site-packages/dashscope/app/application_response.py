# Copyright (c) Alibaba, Inc. and its affiliates.
"""
@File    :   application_response.py
@Date    :   2024-02-24
@Desc    :   application call response
"""
from dataclasses import dataclass
from http import HTTPStatus
from typing import Dict, List, Optional

from dashscope.api_entities.dashscope_response import (DashScopeAPIResponse,
                                                       DictMixin)


@dataclass(init=False)
class ApplicationThought(DictMixin):
    thought: str
    action_type: str
    response: str
    action_name: str
    action: str
    action_input_stream: str
    action_input: Dict
    observation: str

    def __init__(self,
                 thought: str = None,
                 action_type: str = None,
                 response: str = None,
                 action_name: str = None,
                 action: str = None,
                 action_input_stream: str = None,
                 action_input: Dict = None,
                 observation: str = None,
                 **kwargs):
        """ Thought of app completion call result which describe model planning and doc retrieval
            or plugin calls details.

        Args:
            thought (str, optional): Model's inference thought for doc retrieval or plugin process.
            action_type (str, optional): Action type. response : final response; api: to run api calls.
            response (str, optional): Model's results.
            action_name (str, optional): Action name, e.g. searchDocument、api.
            action (str, optional): Code of action, means which plugin or action to be run.
            action_input_stream (str, optional): Input param with stream.
            action_input (dict, optional): Api or plugin input parameters.
            observation (str, optional): Result of api call or doc retrieval.
        """

        super().__init__(thought=thought,
                         action_type=action_type,
                         response=response,
                         action_name=action_name,
                         action=action,
                         action_input_stream=action_input_stream,
                         action_input=action_input,
                         observation=observation,
                         **kwargs)


@dataclass(init=False)
class ApplicationDocReference(DictMixin):
    index_id: str
    title: str
    doc_id: str
    doc_name: str
    doc_url: str
    text: str
    biz_id: str
    images: List[str]
    page_number: List[int]

    def __init__(self,
                 index_id: str = None,
                 title: str = None,
                 doc_id: str = None,
                 doc_name: str = None,
                 doc_url: str = None,
                 text: str = None,
                 biz_id: str = None,
                 images: List[str] = None,
                 page_number: List[int] = None,
                 **kwargs):
        """ Doc references for retrieval result.

        Args:
            index_id (str, optional): Index id of doc retrival result reference.
            title (str, optional): Title of original doc that retrieved.
            doc_id (str, optional): Id of original doc that retrieved.
            doc_name (str, optional): Name of original doc that retrieved.
            doc_url (str, optional): Url of original doc that retrieved.
            text (str, optional): Text in original doc that retrieved.
            biz_id (str, optional): Biz id that caller is able to associated for biz logic.
            images (list, optional): List of referenced image URLs
        """

        super().__init__(index_id=index_id,
                         title=title,
                         doc_id=doc_id,
                         doc_name=doc_name,
                         doc_url=doc_url,
                         text=text,
                         biz_id=biz_id,
                         images=images,
                         page_number=page_number,
                         **kwargs)

@dataclass(init=False)
class WorkflowMessage(DictMixin):
    node_id: str
    node_name: str
    node_type: str
    node_status: str
    node_is_completed: str
    node_msg_seq_id: int
    message: str

    class Message(DictMixin):
        role: str
        content: str

    def __init__(self,
                 node_id: str = None,
                 node_name: str = None,
                 node_type: str = None,
                 node_status: str = None,
                 node_is_completed: str = None,
                 node_msg_seq_id: int = None,
                 message: Message = None,
                 **kwargs):
        """ Workflow message.

        Args:
            node_id (str, optional): .
            node_name (str, optional): .
            node_type (str, optional): .
            node_status (str, optional): .
            node_is_completed (str, optional): .
            node_msg_seq_id (int, optional): .
            message (Message, optional): .
        """

        super().__init__(node_id=node_id,
                         node_name=node_name,
                         node_type=node_type,
                         node_status=node_status,
                         node_is_completed=node_is_completed,
                         node_msg_seq_id=node_msg_seq_id,
                         message=message,
                         **kwargs)


@dataclass(init=False)
class ApplicationOutput(DictMixin):
    text: str
    finish_reason: str
    session_id: str
    thoughts: List[ApplicationThought]
    doc_references: List[ApplicationDocReference]
    workflow_message: WorkflowMessage

    def __init__(self,
                 text: str = None,
                 finish_reason: str = None,
                 session_id: str = None,
                 thoughts: List[ApplicationThought] = None,
                 doc_references: List[ApplicationDocReference] = None,
                 workflow_message: WorkflowMessage = None,
                 **kwargs):

        ths = None
        if thoughts is not None:
            ths = []
            for thought in thoughts:
                ths.append(ApplicationThought(**thought))

        refs = None
        if doc_references is not None:
            refs = []
            for ref in doc_references:
                refs.append(ApplicationDocReference(**ref))

        super().__init__(text=text,
                         finish_reason=finish_reason,
                         session_id=session_id,
                         thoughts=ths,
                         doc_references=refs,
                         workflow_message=workflow_message,
                         **kwargs)


@dataclass(init=False)
class ApplicationModelUsage(DictMixin):
    model_id: str
    input_tokens: int
    output_tokens: int

    def __init__(self,
                 model_id: str = None,
                 input_tokens: int = 0,
                 output_tokens: int = 0,
                 **kwargs):
        super().__init__(model_id=model_id,
                         input_tokens=input_tokens,
                         output_tokens=output_tokens,
                         **kwargs)


@dataclass(init=False)
class ApplicationUsage(DictMixin):
    models: List[ApplicationModelUsage]

    def __init__(self, models: List[ApplicationModelUsage] = None, **kwargs):
        model_usages = None
        if models is not None:
            model_usages = []
            for model_usage in models:
                model_usages.append(ApplicationModelUsage(**model_usage))

        super().__init__(models=model_usages, **kwargs)


@dataclass(init=False)
class ApplicationResponse(DashScopeAPIResponse):
    output: ApplicationOutput
    usage: ApplicationUsage

    @staticmethod
    def from_api_response(api_response: DashScopeAPIResponse):
        if api_response.status_code == HTTPStatus.OK:
            usage = {}
            if api_response.usage:
                usage = api_response.usage

            return ApplicationResponse(
                status_code=api_response.status_code,
                request_id=api_response.request_id,
                code=api_response.code,
                message=api_response.message,
                output=ApplicationOutput(**api_response.output),
                usage=ApplicationUsage(**usage))
        else:
            return ApplicationResponse(status_code=api_response.status_code,
                                       request_id=api_response.request_id,
                                       code=api_response.code,
                                       message=api_response.message)
