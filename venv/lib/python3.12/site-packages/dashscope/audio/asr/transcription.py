# Copyright (c) Alibaba, Inc. and its affiliates.

import asyncio
import time
from typing import List, Union

import aiohttp

from dashscope.api_entities.dashscope_response import (DashScopeAPIResponse,
                                                       TranscriptionResponse)
from dashscope.client.base_api import BaseAsyncApi
from dashscope.common.constants import ApiProtocol, HTTPMethod
from dashscope.common.logging import logger
from dashscope.common.utils import _get_task_group_and_task


class Transcription(BaseAsyncApi):
    """API for File Transcription models.
    """

    MAX_QUERY_TRY_COUNT = 3

    class Models:
        paraformer_v1 = 'paraformer-v1'
        paraformer_8k_v1 = 'paraformer-8k-v1'
        paraformer_mtl_v1 = 'paraformer-mtl-v1'

    @classmethod
    def call(cls,
             model: str,
             file_urls: List[str],
             phrase_id: str = None,
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> TranscriptionResponse:
        """Transcribe the given files synchronously.

        Args:
            model (str): The requested model_id.
            file_urls (List[str]): List of stored URLs.
            phrase_id (str, `optional`): The ID of phrase.
            workspace (str): The dashscope workspace id.

            **kwargs:
                channel_id (List[int], optional):
                    The selected channel_id of audio file.
                disfluency_removal_enabled(bool, `optional`):
                    Filter mood words, turned off by default.
                diarization_enabled (bool, `optional`):
                    Speech auto diarization, turned off by default.
                speaker_count (int, `optional`): The number of speakers.
                timestamp_alignment_enabled (bool, `optional`):
                    Timestamp-alignment calibration, turned off by default.
                special_word_filter(str, `optional`): Sensitive word filter.
                audio_event_detection_enabled(bool, `optional`):
                    Audio event detection, turned off by default.

        Returns:
            TranscriptionResponse: The result of batch transcription.
        """
        kwargs.update(cls._fill_resource_id(phrase_id, **kwargs))
        kwargs = cls._tidy_kwargs(**kwargs)
        response = super().call(model,
                                file_urls,
                                api_key=api_key,
                                workspace=workspace,
                                **kwargs)
        return TranscriptionResponse.from_api_response(response)

    @classmethod
    def async_call(cls,
                   model: str,
                   file_urls: List[str],
                   phrase_id: str = None,
                   api_key: str = None,
                   workspace: str = None,
                   **kwargs) -> TranscriptionResponse:
        """Transcribe the given files asynchronously,
        return the status of task submission for querying results subsequently.

        Args:
            model (str): The requested model, such as paraformer-16k-1
            file_urls (List[str]): List of stored URLs.
            phrase_id (str, `optional`): The ID of phrase.
            workspace (str): The dashscope workspace id.

        **kwargs:
            channel_id (List[int], optional):
                The selected channel_id of audio file.
            disfluency_removal_enabled(bool, `optional`):
                Filter mood words, turned off by default.
            diarization_enabled (bool, `optional`):
                Speech auto diarization, turned off by default.
            speaker_count (int, `optional`): The number of speakers.
            timestamp_alignment_enabled (bool, `optional`):
                Timestamp-alignment calibration, turned off by default.
            special_word_filter(str, `optional`): Sensitive word filter.
            audio_event_detection_enabled(bool, `optional`):
                Audio event detection, turned off by default.

        Returns:
            TranscriptionResponse: The response including task_id.
        """
        kwargs.update(cls._fill_resource_id(phrase_id, **kwargs))
        kwargs = cls._tidy_kwargs(**kwargs)
        response = cls._launch_request(model,
                                       file_urls,
                                       api_key=api_key,
                                       workspace=workspace,
                                       **kwargs)
        return TranscriptionResponse.from_api_response(response)

    @classmethod
    def fetch(cls,
              task: Union[str, TranscriptionResponse],
              api_key: str = None,
              workspace: str = None,
              **kwargs) -> TranscriptionResponse:
        """Fetch the status of task, including results of batch transcription when task_status is SUCCEEDED.  # noqa: E501

        Args:
            task (Union[str, TranscriptionResponse]): The task_id or
                response including task_id returned from async_call().
            workspace (str): The dashscope workspace id.

        Returns:
            TranscriptionResponse: The status of task_id,
        including results of batch transcription when task_status is SUCCEEDED.
        """
        try_count: int = 0
        while True:
            try:
                response = super().fetch(task,
                                         api_key=api_key,
                                         workspace=workspace,
                                         **kwargs)
            except (asyncio.TimeoutError, aiohttp.ClientConnectorError) as e:
                logger.error(e)
                try_count += 1
                if try_count <= Transcription.MAX_QUERY_TRY_COUNT:
                    time.sleep(2)
                    continue

            try_count = 0
            break

        return TranscriptionResponse.from_api_response(response)

    @classmethod
    def wait(cls,
             task: Union[str, TranscriptionResponse],
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> TranscriptionResponse:
        """Poll task until the final results of transcription is obtained.

        Args:
            task (Union[str, TranscriptionResponse]): The task_id or
                response including task_id returned from async_call().
            workspace (str): The dashscope workspace id.

        Returns:
            TranscriptionResponse: The result of batch transcription.
        """
        response = super().wait(task,
                                api_key=api_key,
                                workspace=workspace,
                                **kwargs)
        return TranscriptionResponse.from_api_response(response)

    @classmethod
    def _launch_request(cls,
                        model: str,
                        files: List[str],
                        api_key: str = None,
                        workspace: str = None,
                        **kwargs) -> DashScopeAPIResponse:
        """Submit transcribe request.

        Args:
            model (str): The requested model, such as paraformer-16k-1
            files (List[str]): List of stored URLs.
            workspace (str): The dashscope workspace id.

        Returns:
            DashScopeAPIResponse: The result of task submission.
        """
        task_name, function = _get_task_group_and_task(__name__)

        try_count: int = 0
        while True:
            try:
                response = super().async_call(model=model,
                                              task_group='audio',
                                              task=task_name,
                                              function=function,
                                              input={'file_urls': files},
                                              api_protocol=ApiProtocol.HTTP,
                                              http_method=HTTPMethod.POST,
                                              api_key=api_key,
                                              workspace=workspace,
                                              **kwargs)
            except (asyncio.TimeoutError, aiohttp.ClientConnectorError) as e:
                logger.error(e)
                try_count += 1
                if try_count <= Transcription.MAX_QUERY_TRY_COUNT:
                    time.sleep(2)
                    continue

            break

        return response

    @classmethod
    def _fill_resource_id(cls, phrase_id: str, **kwargs):
        resources_list: list = []
        if phrase_id is not None and len(phrase_id) > 0:
            item = {'resource_id': phrase_id, 'resource_type': 'asr_phrase'}
            resources_list.append(item)

            if len(resources_list) > 0:
                kwargs['resources'] = resources_list

        return kwargs

    @classmethod
    def _tidy_kwargs(cls, **kwargs):
        for k in kwargs.copy():
            if kwargs[k] is None:
                kwargs.pop(k, None)
        return kwargs
