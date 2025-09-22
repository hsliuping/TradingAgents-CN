# Copyright (c) Alibaba, Inc. and its affiliates.

import asyncio
import time
from typing import List

import aiohttp

from dashscope.client.base_api import BaseApi
from dashscope.common.constants import ApiProtocol, HTTPMethod
from dashscope.common.logging import logger


class VocabularyServiceException(Exception):
    def __init__(self, request_id: str, status_code: int, code: str,
                 error_message: str) -> None:
        self._request_id = request_id
        self._status_code = status_code
        self._code = code
        self._error_message = error_message

    def __str__(self):
        return f'Request: {self._request_id}, Status Code: {self._status_code}, Code: {self._code}, Error Message: {self._error_message}'


class VocabularyService(BaseApi):
    '''
    API for asr vocabulary service
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
            self.model = 'speech-biasing'

    def __call_with_input(self, input):
        try_count = 0
        while True:
            try:
                response = super().call(model=self.model,
                                        task_group='audio',
                                        task='asr',
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
                if try_count <= VocabularyService.MAX_QUERY_TRY_COUNT:
                    time.sleep(2)
                    continue

            break
        logger.debug('>>>>recv', response)
        return response

    def create_vocabulary(self, target_model: str, prefix: str,
                          vocabulary: List[dict]) -> str:
        '''
        创建热词表
        param: target_model 热词表对应的语音识别模型版本
        param: prefix 热词表自定义前缀，仅允许数字和小写字母，小于十个字符。
        param: vocabulary 热词表字典
        return: 热词表标识符 vocabulary_id
        '''
        response = self.__call_with_input(input={
            'action': 'create_vocabulary',
            'target_model': target_model,
            'prefix': prefix,
            'vocabulary': vocabulary,
        }, )
        if response.status_code == 200:
            self._last_request_id = response.request_id
            return response.output['vocabulary_id']
        else:
            raise VocabularyServiceException(response.request_id, response.status_code,
                                             response.code, response.message)

    def list_vocabularies(self,
                          prefix=None,
                          page_index: int = 0,
                          page_size: int = 10) -> List[dict]:
        '''
        查询已创建的所有热词表
        param: prefix 自定义前缀，如果设定则只返回指定前缀的热词表标识符列表。
        param: page_index 查询的页索引
        param: page_size 查询页大小
        return: 热词表标识符列表
        '''
        if prefix:
            response = self.__call_with_input(input={
                'action': 'list_vocabulary',
                'prefix': prefix,
                'page_index': page_index,
                'page_size': page_size,
            }, )
        else:
            response = self.__call_with_input(input={
                'action': 'list_vocabulary',
                'page_index': page_index,
                'page_size': page_size,
            }, )
        if response.status_code == 200:
            self._last_request_id = response.request_id
            return response.output['vocabulary_list']
        else:
            raise VocabularyServiceException(response.request_id, response.status_code,
                                             response.code, response.message)

    def query_vocabulary(self, vocabulary_id: str) -> List[dict]:
        '''
        获取热词表内容
        param: vocabulary_id 热词表标识符
        return: 热词表
        '''
        response = self.__call_with_input(input={
            'action': 'query_vocabulary',
            'vocabulary_id': vocabulary_id,
        }, )
        if response.status_code == 200:
            self._last_request_id = response.request_id
            return response.output
        else:
            raise VocabularyServiceException(response.request_id, response.status_code,
                                             response.code, response.message)

    def update_vocabulary(self, vocabulary_id: str,
                          vocabulary: List[dict]) -> None:
        '''
        用新的热词表替换已有热词表
        param: vocabulary_id 需要替换的热词表标识符
        param: vocabulary 热词表
        '''
        response = self.__call_with_input(input={
            'action': 'update_vocabulary',
            'vocabulary_id': vocabulary_id,
            'vocabulary': vocabulary,
        }, )
        if response.status_code == 200:
            self._last_request_id = response.request_id
            return
        else:
            raise VocabularyServiceException(response.request_id, response.status_code,
                                             response.code, response.message)

    def delete_vocabulary(self, vocabulary_id: str) -> None:
        '''
        删除热词表
        param: vocabulary_id 需要删除的热词表标识符
        '''
        response = self.__call_with_input(input={
            'action': 'delete_vocabulary',
            'vocabulary_id': vocabulary_id,
        }, )
        if response.status_code == 200:
            self._last_request_id = response.request_id
            return
        else:
            raise VocabularyServiceException(response.request_id, response.status_code,
                                             response.code, response.message)

    def get_last_request_id(self):
        return self._last_request_id
