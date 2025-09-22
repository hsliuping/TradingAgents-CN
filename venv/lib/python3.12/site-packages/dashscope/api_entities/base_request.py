# Copyright (c) Alibaba, Inc. and its affiliates.

import os
import platform
from abc import ABC, abstractmethod

from dashscope.common.constants import DASHSCOPE_DISABLE_DATA_INSPECTION_ENV
from dashscope.version import __version__


class BaseRequest(ABC):
    def __init__(self) -> None:
        ua = 'dashscope/%s; python/%s; platform/%s; processor/%s' % (
            __version__,
            platform.python_version(),
            platform.platform(),
            platform.processor(),
        )
        self.headers = {'user-agent': ua}
        disable_data_inspection = os.environ.get(
            DASHSCOPE_DISABLE_DATA_INSPECTION_ENV, 'true')

        if (disable_data_inspection.lower() == 'false'):
            self.headers['X-DashScope-DataInspection'] = 'enable'

    @abstractmethod
    def call(self):
        raise NotImplementedError()


class AioBaseRequest(BaseRequest):
    @abstractmethod
    async def aio_call(self):
        raise NotImplementedError()
