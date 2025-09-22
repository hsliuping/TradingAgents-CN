# Copyright (c) Alibaba, Inc. and its affiliates.

from typing import Any, Dict, List, Union

from dashscope.api_entities.dashscope_response import (DashScopeAPIResponse,
                                                       ImageSynthesisResponse)
from dashscope.client.base_api import BaseAsyncApi
from dashscope.common.constants import IMAGES, NEGATIVE_PROMPT, PROMPT
from dashscope.common.error import InputRequired
from dashscope.common.utils import _get_task_group_and_task
from dashscope.utils.oss_utils import check_and_upload_local


class ImageSynthesis(BaseAsyncApi):
    task = 'text2image'
    """API for image synthesis.
    """
    class Models:
        wanx_v1 = 'wanx-v1'
        wanx_sketch_to_image_v1 = 'wanx-sketch-to-image-v1'

        wanx_2_1_imageedit = 'wanx2.1-imageedit'

    @classmethod
    def call(cls,
             model: str,
             prompt: Any,
             negative_prompt: Any = None,
             images: List[str] = None,
             api_key: str = None,
             sketch_image_url: str = None,
             ref_img: str = None,
             workspace: str = None,
             extra_input: Dict = None,
             task: str = None,
             function: str = None,
             mask_image_url: str = None,
             base_image_url: str = None,
             **kwargs) -> ImageSynthesisResponse:
        """Call image(s) synthesis service and get result.

        Args:
            model (str): The model, reference ``Models``.
            prompt (Any): The prompt for image(s) synthesis.
            negative_prompt (Any): The negative_prompt. Defaults to None.
            images (List[str]): The input list of images url,
                currently not supported.
            api_key (str, optional): The api api_key. Defaults to None.
            sketch_image_url (str, optional): Only for wanx-sketch-to-image-v1,
                can be local file.
                Defaults to None.
            workspace (str): The dashscope workspace id.
            extra_input (Dict): The extra input parameters.
            task (str): The task of api, ref doc.
            function (str): The specific functions to be achieved. like:
                colorization,super_resolution,expand,remove_watermaker,doodle,
                description_edit_with_mask,description_edit,stylization_local,stylization_all
            base_image_url (str): Enter the URL address of the target edited image.
            mask_image_url (str): Provide the URL address of the image of the marked area by the user. It should be consistent with the image resolution of the base_image_url.
            **kwargs:
                n(int, `optional`): Number of images to synthesis.
                size(str, `optional`): The output image(s) size(width*height).
                similarity(float, `optional`): The similarity between the
                    output image and the input image
                sketch_weight(int, optional): How much the input sketch
                    affects the output image[0-10], only for wanx-sketch-to-image-v1. # noqa E501
                    Default 10.
                realisticness(int, optional): The realisticness of the output
                    image[0-10], only for wanx-sketch-to-image-v1. Default 5

        Raises:
            InputRequired: The prompt cannot be empty.

        Returns:
            ImageSynthesisResponse: The image(s) synthesis result.
        """
        return super().call(model,
                            prompt,
                            negative_prompt,
                            images,
                            api_key=api_key,
                            sketch_image_url=sketch_image_url,
                            ref_img=ref_img,
                            workspace=workspace,
                            extra_input=extra_input,
                            task=task,
                            function=function,
                            mask_image_url=mask_image_url,
                            base_image_url=base_image_url,
                            **kwargs)

    @classmethod
    def async_call(cls,
                   model: str,
                   prompt: Any,
                   negative_prompt: Any = None,
                   images: List[str] = None,
                   api_key: str = None,
                   sketch_image_url: str = None,
                   ref_img: str = None,
                   workspace: str = None,
                   extra_input: Dict = None,
                   task: str = None,
                   function: str = None,
                   mask_image_url: str = None,
                   base_image_url: str = None,
                   **kwargs) -> ImageSynthesisResponse:
        """Create a image(s) synthesis task, and return task information.

        Args:
            model (str): The model, reference ``Models``.
            prompt (Any): The prompt for image(s) synthesis.
            negative_prompt (Any): The negative_prompt. Defaults to None.
            images (List[str]): The input list of images url.
            api_key (str, optional): The api api_key. Defaults to None.
            sketch_image_url (str, optional): Only for wanx-sketch-to-image-v1.
                Defaults to None.
            workspace (str): The dashscope workspace id.
            extra_input (Dict): The extra input parameters.
            task (str): The task of api, ref doc.
            function (str): The specific functions to be achieved. like:
                colorization,super_resolution,expand,remove_watermaker,doodle,
                description_edit_with_mask,description_edit,stylization_local,stylization_all
            base_image_url (str): Enter the URL address of the target edited image.
            mask_image_url (str): Provide the URL address of the image of the marked area by the user. It should be consistent with the image resolution of the base_image_url.
            **kwargs(wanx-v1):
                n(int, `optional`): Number of images to synthesis.
                size: The output image(s) size, Default 1024*1024
                similarity(float, `optional`): The similarity between the
                    output image and the input image.
                sketch_weight(int, optional): How much the input sketch
                    affects the output image[0-10], only for wanx-sketch-to-image-v1. # noqa E501
                    Default 10.
                realisticness(int, optional): The realisticness of the output
                    image[0-10], only for wanx-sketch-to-image-v1. Default 5

        Raises:
            InputRequired: The prompt cannot be empty.

        Returns:
            DashScopeAPIResponse: The image synthesis
                task id in the response.
        """
        if prompt is None or not prompt:
            raise InputRequired('prompt is required!')
        task_group, f = _get_task_group_and_task(__name__)
        input = {PROMPT: prompt}
        has_upload = False
        if negative_prompt is not None:
            input[NEGATIVE_PROMPT] = negative_prompt
        if images is not None:
            input[IMAGES] = images
        if sketch_image_url is not None and sketch_image_url:
            is_upload, sketch_image_url = check_and_upload_local(
                model, sketch_image_url, api_key)
            if is_upload:
                has_upload = True
            input['sketch_image_url'] = sketch_image_url
        if ref_img is not None and ref_img:
            is_upload, ref_img = check_and_upload_local(
                model, ref_img, api_key)
            if is_upload:
                has_upload = True
            input['ref_img'] = ref_img

        if function is not None and function:
            input['function'] = function

        if mask_image_url is not None and mask_image_url:
            is_upload, res_mask_image_url = check_and_upload_local(
                model, mask_image_url, api_key)
            if is_upload:
                has_upload = True
            input['mask_image_url'] = res_mask_image_url

        if base_image_url is not None and base_image_url:
            is_upload, res_base_image_url = check_and_upload_local(
                model, base_image_url, api_key)
            if is_upload:
                has_upload = True
            input['base_image_url'] = res_base_image_url

        if extra_input is not None and extra_input:
            input = {**input, **extra_input}

        if has_upload:
            headers = kwargs.pop('headers', {})
            headers['X-DashScope-OssResourceResolve'] = 'enable'
            kwargs['headers'] = headers

        if task is None:
            task = ImageSynthesis.task
        if model is not None and model and 'imageedit' in model:
            task = 'image2image'

        response = super().async_call(
            model=model,
            task_group=task_group,
            task=task,
            function=f,
            api_key=api_key,
            input=input,
            workspace=workspace,
            **kwargs)
        return ImageSynthesisResponse.from_api_response(response)

    @classmethod
    def fetch(cls,
              task: Union[str, ImageSynthesisResponse],
              api_key: str = None,
              workspace: str = None) -> ImageSynthesisResponse:
        """Fetch image(s) synthesis task status or result.

        Args:
            task (Union[str, ImageSynthesisResponse]): The task_id or
                ImageSynthesisResponse return by async_call().
            api_key (str, optional): The api api_key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            ImageSynthesisResponse: The task status or result.
        """
        response = super().fetch(task, api_key=api_key, workspace=workspace)
        return ImageSynthesisResponse.from_api_response(response)

    @classmethod
    def wait(cls,
             task: Union[str, ImageSynthesisResponse],
             api_key: str = None,
             workspace: str = None) -> ImageSynthesisResponse:
        """Wait for image(s) synthesis task to complete, and return the result.

        Args:
            task (Union[str, ImageSynthesisResponse]): The task_id or
                ImageSynthesisResponse return by async_call().
            api_key (str, optional): The api api_key. Defaults to None.
            workspace (str): The dashscope workspace id.

        Returns:
            ImageSynthesisResponse: The task result.
        """
        response = super().wait(task, api_key, workspace=workspace)
        return ImageSynthesisResponse.from_api_response(response)

    @classmethod
    def cancel(cls,
               task: Union[str, ImageSynthesisResponse],
               api_key: str = None,
               workspace: str = None) -> DashScopeAPIResponse:
        """Cancel image synthesis task.
        Only tasks whose status is PENDING can be canceled.

        Args:
            task (Union[str, ImageSynthesisResponse]): The task_id or
                ImageSynthesisResponse return by async_call().
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
