# Copyright (c) Alibaba, Inc. and its affiliates.

from typing import Any, Dict, Union

from dashscope.api_entities.dashscope_response import (DashScopeAPIResponse,
                                                       VideoSynthesisResponse)
from dashscope.client.base_api import BaseAsyncApi
from dashscope.common.constants import PROMPT
from dashscope.common.error import InputRequired
from dashscope.common.utils import _get_task_group_and_task
from dashscope.utils.oss_utils import check_and_upload_local


class VideoSynthesis(BaseAsyncApi):
    task = 'video-generation'
    """API for video synthesis.
    """
    class Models:
        """@deprecated, use wanx2.1-t2v-plus instead"""
        wanx_txt2video_pro = 'wanx-txt2video-pro'
        """@deprecated, use wanx2.1-i2v-plus instead"""
        wanx_img2video_pro = 'wanx-img2video-pro'

        wanx_2_1_t2v_turbo = 'wanx2.1-t2v-turbo'
        wanx_2_1_t2v_plus = 'wanx2.1-t2v-plus'

        wanx_2_1_i2v_plus = 'wanx2.1-i2v-plus'
        wanx_2_1_i2v_turbo = 'wanx2.1-i2v-turbo'

        wanx_2_1_kf2v_plus = 'wanx2.1-kf2v-plus'
        wanx_kf2v = 'wanx-kf2v'

    @classmethod
    def call(cls,
             model: str,
             prompt: Any = None,
             # """@deprecated, use prompt_extend in parameters """
             extend_prompt: bool = True,
             negative_prompt: str = None,
             template: str = None,
             img_url: str = None,
             api_key: str = None,
             extra_input: Dict = None,
             workspace: str = None,
             task: str = None,
             head_frame: str = None,
             tail_frame: str = None,
             first_frame_url: str = None,
             last_frame_url: str = None,
             **kwargs) -> VideoSynthesisResponse:
        """Call video synthesis service and get result.

        Args:
            model (str): The model, reference ``Models``.
            prompt (Any): The prompt for video synthesis.
            extend_prompt (bool): @deprecated, use prompt_extend in parameters
            negative_prompt (str): The negative prompt is the opposite of the prompt meaning.
            template (str): LoRa input, such as gufeng, katong, etc.
            img_url (str): The input image url, Generate the URL of the image referenced by the video.
            api_key (str, optional): The api api_key. Defaults to None.
            workspace (str): The dashscope workspace id.
            extra_input (Dict): The extra input parameters.
            task (str): The task of api, ref doc.
            first_frame_url (str): The URL of the first frame image for generating the video.
            last_frame_url (str): The URL of the last frame image for generating the video.
            **kwargs:
                size(str, `optional`): The output video size(width*height).
                duration(int, optional): The duration. Duration of video generation. The default value is 5, in seconds.
                seed(int, optional): The seed. The random seed for video generation. The default value is 5.

        Raises:
            InputRequired: The prompt cannot be empty.

        Returns:
            VideoSynthesisResponse: The video synthesis result.
        """
        return super().call(model,
                            prompt,
                            img_url=img_url,
                            api_key=api_key,
                            extend_prompt=extend_prompt,
                            negative_prompt=negative_prompt,
                            template=template,
                            workspace=workspace,
                            extra_input=extra_input,
                            task=task,
                            head_frame=head_frame,
                            tail_frame=tail_frame,
                            first_frame_url=first_frame_url,
                            last_frame_url=last_frame_url,
                            **kwargs)

    @classmethod
    def async_call(cls,
                   model: str,
                   prompt: Any = None,
                   img_url: str = None,
                   # """@deprecated, use prompt_extend in parameters """
                   extend_prompt: bool = True,
                   negative_prompt: str = None,
                   template: str = None,
                   api_key: str = None,
                   extra_input: Dict = None,
                   workspace: str = None,
                   task: str = None,
                   head_frame: str = None,
                   tail_frame: str = None,
                   first_frame_url: str = None,
                   last_frame_url: str = None,
                   **kwargs) -> VideoSynthesisResponse:
        """Create a video synthesis task, and return task information.

        Args:
            model (str): The model, reference ``Models``.
            prompt (Any): The prompt for video synthesis.
            extend_prompt (bool): @deprecated, use prompt_extend in parameters
            negative_prompt (str): The negative prompt is the opposite of the prompt meaning.
            template (str): LoRa input, such as gufeng, katong, etc.
            img_url (str): The input image url, Generate the URL of the image referenced by the video.
            api_key (str, optional): The api api_key. Defaults to None.
            workspace (str): The dashscope workspace id.
            extra_input (Dict): The extra input parameters.
            task (str): The task of api, ref doc.
            first_frame_url (str): The URL of the first frame image for generating the video.
            last_frame_url (str): The URL of the last frame image for generating the video.
            **kwargs:
                size(str, `optional`): The output video size(width*height).
                duration(int, optional): The duration. Duration of video generation. The default value is 5, in seconds.
                seed(int, optional): The seed. The random seed for video generation. The default value is 5.

        Raises:
            InputRequired: The prompt cannot be empty.

        Returns:
            DashScopeAPIResponse: The video synthesis
                task id in the response.
        """
        task_group, function = _get_task_group_and_task(__name__)
        inputs = {PROMPT: prompt, 'extend_prompt': extend_prompt}
        if negative_prompt:
            inputs['negative_prompt'] = negative_prompt
        if template:
            inputs['template'] = template
        if function:
            inputs['function'] = function

        has_upload = False

        if img_url is not None and img_url:
            is_upload, res_img_url = check_and_upload_local(
                model, img_url, api_key)
            if is_upload:
                has_upload = True
            inputs['img_url'] = res_img_url

        if head_frame is not None and head_frame:
            is_upload, res_head_frame = check_and_upload_local(
                model, head_frame, api_key)
            if is_upload:
                has_upload = True
            inputs['head_frame'] = res_head_frame

        if tail_frame is not None and tail_frame:
            is_upload, res_tail_frame = check_and_upload_local(
                model, tail_frame, api_key)
            if is_upload:
                has_upload = True
            inputs['tail_frame'] = res_tail_frame

        if first_frame_url is not None and first_frame_url:
            is_upload, res_first_frame_url = check_and_upload_local(
                model, first_frame_url, api_key)
            if is_upload:
                has_upload = True
            inputs['first_frame_url'] = res_first_frame_url

        if last_frame_url is not None and last_frame_url:
            is_upload, res_last_frame_url = check_and_upload_local(
                model, last_frame_url, api_key)
            if is_upload:
                has_upload = True
            inputs['last_frame_url'] = res_last_frame_url

        if extra_input is not None and extra_input:
            inputs = {**inputs, **extra_input}
        if has_upload:
            headers = kwargs.pop('headers', {})
            headers['X-DashScope-OssResourceResolve'] = 'enable'
            kwargs['headers'] = headers

        if task is None:
            task = VideoSynthesis.task
        if model is not None and model and 'kf2v' in model:
            task = 'image2video'
        response = super().async_call(
            model=model,
            task_group=task_group,
            task=VideoSynthesis.task if task is None else task,
            function=function,
            api_key=api_key,
            input=inputs,
            workspace=workspace,
            **kwargs)
        return VideoSynthesisResponse.from_api_response(response)

    @classmethod
    def fetch(cls,
              task: Union[str, VideoSynthesisResponse],
              api_key: str = None,
              workspace: str = None) -> VideoSynthesisResponse:
        """Fetch video synthesis task status or result.

        Args:
            task (Union[str, VideoSynthesisResponse]): The task_id or
                VideoSynthesisResponse return by async_call().
            api_key (str, optional): The api api_key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            VideoSynthesisResponse: The task status or result.
        """
        response = super().fetch(task, api_key=api_key, workspace=workspace)
        return VideoSynthesisResponse.from_api_response(response)

    @classmethod
    def wait(cls,
             task: Union[str, VideoSynthesisResponse],
             api_key: str = None,
             workspace: str = None) -> VideoSynthesisResponse:
        """Wait for video synthesis task to complete, and return the result.

        Args:
            task (Union[str, VideoSynthesisResponse]): The task_id or
                VideoSynthesisResponse return by async_call().
            api_key (str, optional): The api api_key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            VideoSynthesisResponse: The task result.
        """
        response = super().wait(task, api_key, workspace=workspace)
        return VideoSynthesisResponse.from_api_response(response)

    @classmethod
    def cancel(cls,
               task: Union[str, VideoSynthesisResponse],
               api_key: str = None,
               workspace: str = None) -> DashScopeAPIResponse:
        """Cancel video synthesis task.
        Only tasks whose status is PENDING can be canceled.

        Args:
            task (Union[str, VideoSynthesisResponse]): The task_id or
                VideoSynthesisResponse return by async_call().
            api_key (str, optional): The api api_key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            DashScopeAPIResponse: The response data.
        """
        return super().cancel(task, api_key, workspace=workspace)

    @classmethod
    def list(cls,
             start_time: str = None,
             end_time: str = None,
             model_name: str = None,
             api_key_id: str = None,
             region: str = None,
             status: str = None,
             page_no: int = 1,
             page_size: int = 10,
             api_key: str = None,
             workspace: str = None,
             **kwargs) -> DashScopeAPIResponse:
        """List async tasks.

        Args:
            start_time (str, optional): The tasks start time,
                for example: 20230420000000. Defaults to None.
            end_time (str, optional): The tasks end time,
                for example: 20230420000000. Defaults to None.
            model_name (str, optional): The tasks model name. Defaults to None.
            api_key_id (str, optional): The tasks api-key-id. Defaults to None.
            region (str, optional): The service region,
                for example: cn-beijing. Defaults to None.
            status (str, optional): The status of tasks[PENDING,
                RUNNING, SUCCEEDED, FAILED, CANCELED]. Defaults to None.
            page_no (int, optional): The page number. Defaults to 1.
            page_size (int, optional): The page size. Defaults to 10.
            api_key (str, optional): The user api-key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            DashScopeAPIResponse: The response data.
        """
        return super().list(start_time=start_time,
                            end_time=end_time,
                            model_name=model_name,
                            api_key_id=api_key_id,
                            region=region,
                            status=status,
                            page_no=page_no,
                            page_size=page_size,
                            api_key=api_key,
                            workspace=workspace,
                            **kwargs)
