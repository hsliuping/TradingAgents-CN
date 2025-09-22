from typing import Dict, Any

from dashscope.api_entities.api_request_factory import _build_api_request
from dashscope.api_entities.dashscope_response import DashScopeAPIResponse
from dashscope.client.base_api import BaseApi
from dashscope.common.error import ModelRequired


class TingWu(BaseApi):
    """API for TingWu APP.

    """

    task = None
    task_group = None
    function = None

    @classmethod
    def call(
            cls,
            model: str,
            user_defined_input: Dict[str, Any],
            parameters: Dict[str, Any] = None,
            api_key: str = None,
            **kwargs
    ) -> DashScopeAPIResponse:
        """Call generation model service.

        Args:
            model (str): The requested model, such as qwen-turbo
            api_key (str, optional): The api api_key, can be None,
                if None, will get by default rule(TODO: api key doc).
            user_defined_input: custom input
            parameters: custom parameters
            **kwargs:
                base_address: base address
                additional parameters for request

        Raises:
            InvalidInput: The history and auto_history are mutually exclusive.

        Returns:
            Union[GenerationResponse,
                  Generator[GenerationResponse, None, None]]: If
            stream is True, return Generator, otherwise GenerationResponse.
        """
        if model is None or not model:
            raise ModelRequired('Model is required!')
        input_config, parameters = cls._build_input_parameters(input_config=user_defined_input,
                                                               params=parameters,
                                                               **kwargs)

        request = _build_api_request(
            model=model,
            input=input_config,
            api_key=api_key,
            task_group=TingWu.task_group,
            task=TingWu.task,
            function=TingWu.function,
            is_service=False,
            **parameters)
        response = request.call()

        return response

    @classmethod
    def _build_input_parameters(cls,
                                input_config,
                                params: Dict[str, Any] = None,
                                **kwargs):
        parameters = {}
        if params is not None:
            parameters = params

        input_param = input_config

        if kwargs.keys() is not None:
            for key in kwargs.keys():
                parameters[key] = kwargs[key]
        return input_param, {**parameters, **kwargs}
