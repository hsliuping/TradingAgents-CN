# Copyright (c) Alibaba, Inc. and its affiliates.

from http import HTTPStatus
from typing import Any, Dict

from dashscope.api_entities.dashscope_response import DashScopeAPIResponse
from dashscope.client.base_api import BaseAsyncApi
from dashscope.common.error import InvalidParameter
from dashscope.common.logging import logger
from dashscope.customize.finetunes import FineTunes


class AsrPhraseManager(BaseAsyncApi):
    """Hot word management for speech recognition.
    """
    @classmethod
    def create_phrases(cls,
                       model: str,
                       phrases: Dict[str, Any],
                       training_type: str = 'compile_asr_phrase',
                       workspace: str = None,
                       **kwargs) -> DashScopeAPIResponse:
        """Create hot words.

        Args:
            model (str): The requested model.
            phrases (Dict[str, Any]): A dictionary that contains phrases,
                such as {'下一首':90,'上一首':90}.
            training_type (str, `optional`): The training type,
                'compile_asr_phrase' is default.
            workspace (str): The dashscope workspace id.

        Raises:
            InvalidParameter: Parameter input is None or empty!

        Returns:
            DashScopeAPIResponse: The results of creating hot words.
        """
        if phrases is None or len(phrases) == 0:
            raise InvalidParameter('phrases is empty!')
        if training_type is None or len(training_type) == 0:
            raise InvalidParameter('training_type is empty!')

        original_ft_sub_path = FineTunes.SUB_PATH
        FineTunes.SUB_PATH = 'fine-tunes'
        response = FineTunes.call(model=model,
                                  training_file_ids=[],
                                  validation_file_ids=[],
                                  mode=training_type,
                                  hyper_parameters={'phrase_list': phrases},
                                  workspace=workspace,
                                  **kwargs)
        FineTunes.SUB_PATH = original_ft_sub_path

        if response.status_code != HTTPStatus.OK:
            logger.error('Create phrase failed, ' + str(response))

        return response

    @classmethod
    def update_phrases(cls,
                       model: str,
                       phrase_id: str,
                       phrases: Dict[str, Any],
                       training_type: str = 'compile_asr_phrase',
                       workspace: str = None,
                       **kwargs) -> DashScopeAPIResponse:
        """Update the hot words marked phrase_id.

        Args:
            model (str): The requested model.
            phrase_id (str): The ID of phrases,
                which created by create_phrases().
            phrases (Dict[str, Any]): A dictionary that contains phrases,
                such as {'暂停':90}.
            training_type (str, `optional`):
                The training type, 'compile_asr_phrase' is default.
            workspace (str): The dashscope workspace id.

        Raises:
            InvalidParameter: Parameter input is None or empty!

        Returns:
            DashScopeAPIResponse: The results of updating hot words.
        """
        if phrase_id is None or len(phrase_id) == 0:
            raise InvalidParameter('phrase_id is empty!')
        if phrases is None or len(phrases) == 0:
            raise InvalidParameter('phrases is empty!')
        if training_type is None or len(training_type) == 0:
            raise InvalidParameter('training_type is empty!')

        original_ft_sub_path = FineTunes.SUB_PATH
        FineTunes.SUB_PATH = 'fine-tunes'
        response = FineTunes.call(model=model,
                                  training_file_ids=[],
                                  validation_file_ids=[],
                                  mode=training_type,
                                  hyper_parameters={'phrase_list': phrases},
                                  finetuned_output=phrase_id,
                                  workspace=workspace,
                                  **kwargs)
        FineTunes.SUB_PATH = original_ft_sub_path

        if response.status_code != HTTPStatus.OK:
            logger.error('Update phrase failed, ' + str(response))

        return response

    @classmethod
    def query_phrases(cls,
                      phrase_id: str,
                      workspace: str = None,
                      **kwargs) -> DashScopeAPIResponse:
        """Query the hot words by phrase_id.

        Args:
            phrase_id (str): The ID of phrases,
                which created by create_phrases().
            workspace (str): The dashscope workspace id.

        Raises:
            InvalidParameter: phrase_id input is None or empty!

        Returns:
            AsrPhraseManagerResult: The results of querying hot words.
        """
        if phrase_id is None or len(phrase_id) == 0:
            raise InvalidParameter('phrase_id is empty!')

        original_ft_sub_path = FineTunes.SUB_PATH
        FineTunes.SUB_PATH = 'fine-tunes/outputs'
        response = FineTunes.get(job_id=phrase_id,
                                 workspace=workspace,
                                 **kwargs)
        FineTunes.SUB_PATH = original_ft_sub_path

        if response.status_code != HTTPStatus.OK:
            logger.error('Query phrase failed, ' + str(response))

        return response

    @classmethod
    def list_phrases(cls,
                     page: int = 1,
                     page_size: int = 10,
                     workspace: str = None,
                     **kwargs) -> DashScopeAPIResponse:
        """List all information of phrases.

        Args:
            page (int): Page number, greater than 0, default value 1.
            page_size (int): The paging size, greater than 0
                and less than or equal to 100, default value 10.
            workspace (str): The dashscope workspace id.

        Returns:
            DashScopeAPIResponse: The results of listing hot words.
        """
        original_ft_sub_path = FineTunes.SUB_PATH
        FineTunes.SUB_PATH = 'fine-tunes/outputs'
        response = FineTunes.list(page=page,
                                  page_size=page_size,
                                  workspace=workspace,
                                  **kwargs)
        FineTunes.SUB_PATH = original_ft_sub_path

        if response.status_code != HTTPStatus.OK:
            logger.error('List phrase failed, ' + str(response))

        return response

    @classmethod
    def delete_phrases(cls,
                       phrase_id: str,
                       workspace: str = None,
                       **kwargs) -> DashScopeAPIResponse:
        """Delete the hot words by phrase_id.

        Args:
            phrase_id (str): The ID of phrases,
                which created by create_phrases().

        Raises:
            InvalidParameter: phrase_id input is None or empty!

        Returns:
            DashScopeAPIResponse: The results of deleting hot words.
        """
        if phrase_id is None or len(phrase_id) == 0:
            raise InvalidParameter('phrase_id is empty!')

        original_ft_sub_path = FineTunes.SUB_PATH
        FineTunes.SUB_PATH = 'fine-tunes/outputs'
        response = FineTunes.delete(job_id=phrase_id,
                                    workspace=workspace,
                                    **kwargs)
        FineTunes.SUB_PATH = original_ft_sub_path

        if response.status_code != HTTPStatus.OK:
            logger.error('Delete phrase failed, ' + str(response))

        return response
