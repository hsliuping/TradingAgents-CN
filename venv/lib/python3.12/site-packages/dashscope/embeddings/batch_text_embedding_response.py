# Copyright (c) Alibaba, Inc. and its affiliates.

from http import HTTPStatus

from attr import dataclass

from dashscope.api_entities.dashscope_response import (DashScopeAPIResponse,
                                                       DictMixin)


@dataclass(init=False)
class BatchTextEmbeddingOutput(DictMixin):
    task_id: str
    task_status: str
    url: str

    def __init__(self,
                 task_id: str,
                 task_status: str,
                 url: str = None,
                 **kwargs):
        super().__init__(self,
                         task_id=task_id,
                         task_status=task_status,
                         url=url,
                         **kwargs)


@dataclass(init=False)
class BatchTextEmbeddingUsage(DictMixin):
    total_tokens: int

    def __init__(self, total_tokens: int=None, **kwargs):
        super().__init__(total_tokens=total_tokens, **kwargs)


@dataclass(init=False)
class BatchTextEmbeddingResponse(DashScopeAPIResponse):
    output: BatchTextEmbeddingOutput
    usage: BatchTextEmbeddingUsage

    @staticmethod
    def from_api_response(api_response: DashScopeAPIResponse):
        if api_response.status_code == HTTPStatus.OK:
            output = None
            usage = None
            if api_response.output is not None:
                output = BatchTextEmbeddingOutput(**api_response.output)
            if api_response.usage is not None:
                usage = BatchTextEmbeddingUsage(**api_response.usage)

            return BatchTextEmbeddingResponse(
                status_code=api_response.status_code,
                request_id=api_response.request_id,
                code=api_response.code,
                message=api_response.message,
                output=output,
                usage=usage)

        else:
            return BatchTextEmbeddingResponse(
                status_code=api_response.status_code,
                request_id=api_response.request_id,
                code=api_response.code,
                message=api_response.message)
