# Copyright (c) Alibaba, Inc. and its affiliates.

from dataclasses import dataclass
from http import HTTPStatus
from typing import Dict, List

from dashscope.common.base_type import BaseObjectMixin

__all__ = ['Deployment', 'FineTune', 'DeploymentList', 'FineTuneList']


@dataclass(init=False)
class DashScopeBaseList(BaseObjectMixin):
    page_no: int
    page_size: int
    total: int

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class DashScopeBase(BaseObjectMixin):
    status_code: int
    request_id: str
    code: str
    message: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class FineTuneOutput(BaseObjectMixin):
    job_id: str
    job_name: str
    status: str
    model: str
    base_model: str
    finetuned_output: str
    training_file_ids: List[str]
    validation_file_ids: List[str]
    hyper_parameters: Dict
    training_type: str
    create_time: str
    end_time: str
    user_identity: str
    modifier: str
    creator: str
    group: str
    usage: int

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class FineTune(DashScopeBase):
    output: FineTuneOutput
    usage: Dict

    def __init__(self, **kwargs):
        status_code = kwargs.get('status_code', None)
        if status_code == HTTPStatus.OK:
            self.output = FineTuneOutput(**kwargs.pop('output', {}))
        super().__init__(**kwargs)


@dataclass(init=False)
class FineTuneListOutput(DashScopeBaseList):
    jobs: List[FineTuneOutput]

    def __init__(self, **kwargs):
        self.jobs = []
        for job in kwargs.pop('jobs', []):
            self.jobs.append(FineTuneOutput(**job))
        super().__init__(**kwargs)


@dataclass(init=False)
class FineTuneList(DashScopeBase):
    output: FineTuneListOutput

    def __init__(self, **kwargs):
        status_code = kwargs.get('status_code', None)
        if status_code == HTTPStatus.OK:
            self.output = FineTuneListOutput(**kwargs.pop('output', {}))
        super().__init__(**kwargs)


@dataclass(init=False)
class CancelDeleteStatus(BaseObjectMixin):
    status: str


@dataclass(init=False)
class FineTuneCancel(DashScopeBase):
    output: CancelDeleteStatus

    def __init__(self, **kwargs):
        status_code = kwargs.get('status_code', None)
        if status_code == HTTPStatus.OK:
            self.output = CancelDeleteStatus(**kwargs.pop('output', {}))
        super().__init__(**kwargs)


@dataclass(init=False)
class FineTuneDelete(DashScopeBase):
    output: CancelDeleteStatus

    def __init__(self, **kwargs):
        status_code = kwargs.get('status_code', None)
        if status_code == HTTPStatus.OK:
            self.output = CancelDeleteStatus(**kwargs.pop('output', {}))
        super().__init__(**kwargs)


@dataclass(init=False)
class FineTuneEvent(DashScopeBase):
    output: str

    def __init__(self, **kwargs):
        status_code = kwargs.get('status_code', None)
        if status_code == HTTPStatus.OK:
            self.output = kwargs.pop('output', {})
        super().__init__(**kwargs)


@dataclass(init=False)
class DeploymentOutput(BaseObjectMixin):
    deployed_model: str
    gmt_create: str
    gmt_modified: str
    status: str
    model_name: str
    base_model: str
    base_capacity: int
    capacity: int
    ready_capacity: int
    workspace_id: str
    charge_type: str
    modifier: str
    creator: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@dataclass(init=False)
class Deployment(DashScopeBase):
    output: DeploymentOutput

    def __init__(self, **kwargs):
        output = kwargs.pop('output', {})
        if output:
            self.output = DeploymentOutput(**output)
        else:
            self.output = None
        super().__init__(**kwargs)


@dataclass(init=False)
class DeploymentListOutput(DashScopeBaseList):
    deployments: List[DeploymentOutput]

    def __init__(self, **kwargs):
        self.deployments = []
        for job in kwargs.pop('deployments', []):
            self.deployments.append(DeploymentOutput(**job))
        super().__init__(**kwargs)


@dataclass(init=False)
class DeploymentList(BaseObjectMixin):
    output: DeploymentListOutput

    def __init__(self, **kwargs):
        status_code = kwargs.get('status_code', None)
        if status_code == HTTPStatus.OK:
            self.output = DeploymentListOutput(**kwargs.pop('output', {}))
        super().__init__(**kwargs)


@dataclass(init=False)
class DeploymentDelete(DashScopeBase):
    output: CancelDeleteStatus

    def __init__(self, **kwargs):
        status_code = kwargs.get('status_code', None)
        if status_code == HTTPStatus.OK:
            self.output = CancelDeleteStatus(**kwargs.pop('output', {}))
        super().__init__(**kwargs)
