# Copyright (c) Alibaba, Inc. and its affiliates.

import time
from http import HTTPStatus
from typing import Iterator, Union

from dashscope.client.base_api import (CancelMixin, CreateMixin, DeleteMixin,
                                       GetStatusMixin, ListMixin, LogMixin,
                                       StreamEventMixin)
from dashscope.common.constants import TaskStatus
from dashscope.customize.customize_types import (FineTune, FineTuneCancel,
                                                 FineTuneDelete, FineTuneEvent,
                                                 FineTuneList)


class FineTunes(CreateMixin, CancelMixin, DeleteMixin, ListMixin,
                GetStatusMixin, StreamEventMixin, LogMixin):
    SUB_PATH = 'fine-tunes'

    @classmethod
    def call(cls,
             model: str,
             training_file_ids: Union[list, str],
             validation_file_ids: Union[list, str] = None,
             mode: str = None,
             hyper_parameters: dict = {},
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> FineTune:
        """Create fine-tune job

        Args:
            model (str): The model to be fine-tuned
            training_file_ids (list, str): Ids of the fine-tune training data,
                which can be pre-uploaded using the File API.
            validation_file_ids ([list,str], optional): Ids of the fine-tune
                validating data, which can be pre-uploaded using the File API.
            mode (str): The fine-tune mode, sft or efficient_sft.
            hyper_parameters (dict, optional): The fine-tune hyper parameters.
                Defaults to empty.
            api_key (str, optional): The api key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            FineTune: The request result.
        """
        if isinstance(training_file_ids, str):
            training_file_ids = [training_file_ids]
        if validation_file_ids and isinstance(validation_file_ids, str):
            validation_file_ids = [validation_file_ids]
        request = {
            'model': model,
            'training_file_ids': training_file_ids,
            'validation_file_ids': validation_file_ids,
            'hyper_parameters': hyper_parameters if hyper_parameters else {},
        }
        if mode is not None:
            request['training_type'] = mode
        if 'finetuned_output' in kwargs:
            request['finetuned_output'] = kwargs['finetuned_output']
        resp = super().call(request,
                            api_key=api_key,
                            workspace=workspace,
                            **kwargs)
        return FineTune(**resp)

    @classmethod
    def cancel(cls,
               job_id: str,
               api_key: str = None,
               workspace: str = None,
               **kwargs) -> FineTuneCancel:
        """Cancel a running fine-tune job.

        Args:
            job_id (str): The fine-tune job id.
            api_key (str, optional): The api api_key, can be None,
                if None, will get by default rule(TODO: api key doc).
            workspace (str): The dashscope workspace id.

        Returns:
            FineTune: The request result.
        """
        rsp = super().cancel(job_id,
                             api_key=api_key,
                             workspace=workspace,
                             **kwargs)
        return FineTuneCancel(**rsp)

    @classmethod
    def list(cls,
             page_no=1,
             page_size=10,
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> FineTuneList:
        """List fine-tune job.

        Args:
            api_key (str, optional): The api key
            page_no (int, optional): Page number. Defaults to 1.
            page_size (int, optional): Items per page. Defaults to 10.
            workspace (str): The dashscope workspace id.

        Returns:
            FineTune: The fine-tune jobs in the result.
        """
        response = super().list(page_no=page_no,
                                page_size=page_size,
                                api_key=api_key,
                                workspace=workspace,
                                **kwargs)
        return FineTuneList(**response)

    @classmethod
    def get(cls,
            job_id: str,
            api_key: str = None,
            workspace: str = None,
            **kwargs) -> FineTune:
        """Get fine-tune job information.

        Args:
            job_id (str): The fine-tune job id
            api_key (str, optional): The api key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            FineTune: The job info
        """
        response = super().get(job_id,
                               api_key=api_key,
                               workspace=workspace,
                               **kwargs)
        return FineTune(**response)

    @classmethod
    def delete(cls,
               job_id: str,
               api_key: str = None,
               workspace: str = None,
               **kwargs) -> FineTuneDelete:
        """Delete a fine-tune job.

        Args:
            job_id (str): The fine-tune job id.
            api_key (str, optional): The api key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            FineTune: The delete result.
        """
        rsp = super().delete(job_id,
                             api_key=api_key,
                             workspace=workspace,
                             **kwargs)
        return FineTuneDelete(**rsp)

    @classmethod
    def stream_events(cls,
                      job_id: str,
                      api_key: str = None,
                      workspace: str = None,
                      **kwargs) -> Iterator[FineTuneEvent]:
        """Get fine-tune job events.

        Args:
            job_id (str): The fine-tune job id
            api_key (str, optional): the api key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            FineTune: The job log events.
        """
        responses = super().stream_events(job_id,
                                          api_key=api_key,
                                          workspace=workspace,
                                          **kwargs)
        for rsp in responses:
            yield FineTuneEvent(**rsp)

    @classmethod
    def logs(cls,
             job_id: str,
             *,
             offset=1,
             line=1000,
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> FineTune:
        """Get log of the job.

        Args:
            job_id (str): The job id(used for fine-tune)
            offset (int, optional): start log line. Defaults to 1.
            line (int, optional): total line return. Defaults to 1000.
            api_key (str, optional): The api key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            FineTune: The response
        """
        return super().logs(job_id,
                            offset=offset,
                            line=line,
                            workspace=workspace,
                            api_key=api_key)

    @classmethod
    def wait(cls,
             job_id: str,
             api_key: str = None,
             workspace: str = None,
             **kwargs):
        try:
            while True:
                rsp = FineTunes.get(job_id,
                                    api_key=api_key,
                                    workspace=workspace,
                                    **kwargs)
                if rsp.status_code == HTTPStatus.OK:
                    if rsp.output['status'] in [
                            TaskStatus.FAILED, TaskStatus.CANCELED,
                            TaskStatus.SUCCEEDED
                    ]:
                        return rsp
                    else:
                        time.sleep(30)
                else:
                    return rsp
        except Exception:
            raise Exception(
                'You can stream output via: dashscope fine_tunes.stream -j %s'
                % job_id)
