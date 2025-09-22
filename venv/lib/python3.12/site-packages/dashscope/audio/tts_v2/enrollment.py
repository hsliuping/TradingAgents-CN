# Copyright (c) Alibaba, Inc. and its affiliates.

import asyncio
import time
from typing import List

import aiohttp

from dashscope.client.base_api import BaseApi
from dashscope.common.constants import ApiProtocol, HTTPMethod
from dashscope.common.logging import logger


class VoiceEnrollmentException(Exception):
    def __init__(self, request_id: str, status_code: int, code: str,
                 error_message: str) -> None:
        self._request_id = request_id
        self._status_code = status_code
        self._code = code
        self._error_message = error_message

    def __str__(self):
        return f'Request: {self._request_id}, Status Code: {self._status_code}, Code: {self._code}, Error Message: {self._error_message}'


class VoiceEnrollmentService(BaseApi):
    '''
    API for voice clone service
    '''
    MAX_QUERY_TRY_COUNT = 3

    def __init__(self,
                 api_key=None,
                 workspace=None,
                 model=None,
                 **kwargs) -> None:
        super().__init__()
        self._api_key = api_key
        self._workspace = workspace
        self._kwargs = kwargs
        self._last_request_id = None
        self.model = model
        if self.model is None:
            self.model = 'voice-enrollment'

    def __call_with_input(self, input):
        try_count = 0
        while True:
            try:
                response = super().call(model=self.model,
                                        task_group='audio',
                                        task='tts',
                                        function='customization',
                                        input=input,
                                        api_protocol=ApiProtocol.HTTP,
                                        http_method=HTTPMethod.POST,
                                        api_key=self._api_key,
                                        workspace=self._workspace,
                                        **self._kwargs)
            except (asyncio.TimeoutError, aiohttp.ClientConnectorError) as e:
                logger.error(e)
                try_count += 1
                if try_count <= VoiceEnrollmentService.MAX_QUERY_TRY_COUNT:
                    time.sleep(2)
                    continue

            break
        logger.debug('>>>>recv', response)
        return response

    def create_voice(self, target_model: str, prefix: str, url: str) -> str:
        '''
        创建新克隆音色
        param: target_model 克隆音色对应的语音合成模型版本
        param: prefix 音色自定义前缀，仅允许数字和小写字母，小于十个字符。
        param: url 用于克隆的音频文件url
        return: voice_id
        '''
        response = self.__call_with_input(input={
            'action': 'create_voice',
            'target_model': target_model,
            'prefix': prefix,
            'url': url,
        }, )
        self._last_request_id = response.request_id
        if response.status_code == 200:
            return response.output['voice_id']
        else:
            raise VoiceEnrollmentException(response.request_id, response.status_code, response.code,
                                           response.message)

    def list_voices(self,
                    prefix=None,
                    page_index: int = 0,
                    page_size: int = 10) -> List[dict]:
        '''
        查询已创建的所有音色
        param: page_index 查询的页索引
        param: page_size 查询页大小
        return: List[dict] 音色列表，包含每个音色的id，创建时间，修改时间，状态。
        '''
        if prefix:
            response = self.__call_with_input(input={
                'action': 'list_voice',
                'prefix': prefix,
                'page_index': page_index,
                'page_size': page_size,
            }, )
        else:
            response = self.__call_with_input(input={
                'action': 'list_voice',
                'page_index': page_index,
                'page_size': page_size,
            }, )
        self._last_request_id = response.request_id
        if response.status_code == 200:
            return response.output['voice_list']
        else:
            raise VoiceEnrollmentException(response.request_id, response.status_code, response.code,
                                           response.message)

    def query_voice(self, voice_id: str) -> List[str]:
        '''
        查询已创建的所有音色
        param: voice_id 需要查询的音色
        return: bytes 注册音色使用的音频
        '''
        response = self.__call_with_input(input={
            'action': 'query_voice',
            'voice_id': voice_id,
        }, )
        self._last_request_id = response.request_id
        if response.status_code == 200:
            return response.output
        else:
            raise VoiceEnrollmentException(response.request_id, response.status_code, response.code,
                                           response.message)

    def update_voice(self, voice_id: str, url: str) -> None:
        '''
        更新音色
        param: voice_id 音色id
        param: url 用于克隆的音频文件url
        '''
        response = self.__call_with_input(input={
            'action': 'update_voice',
            'voice_id': voice_id,
            'url': url,
        }, )
        self._last_request_id = response.request_id
        if response.status_code == 200:
            return
        else:
            raise VoiceEnrollmentException(response.request_id, response.status_code, response.code,
                                           response.message)

    def delete_voice(self, voice_id: str) -> None:
        '''
        删除音色
        param: voice_id 需要删除的音色
        '''
        response = self.__call_with_input(input={
            'action': 'delete_voice',
            'voice_id': voice_id,
        }, )
        self._last_request_id = response.request_id
        if response.status_code == 200:
            return
        else:
            raise VoiceEnrollmentException(response.request_id, response.status_code, response.code,
                                           response.message)

    def get_last_request_id(self):
        return self._last_request_id
