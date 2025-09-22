# Copyright (c) Alibaba, Inc. and its affiliates.

import json
from urllib.parse import urlencode

import aiohttp

from dashscope.common.constants import ApiProtocol
from dashscope.io.input_output import InputResolver


class ApiRequestData():
    def __init__(
        self,
        model,
        task_group,
        task,
        function,
        input,
        form,
        is_binary_input,
        api_protocol,
    ) -> None:
        self.model = model
        self.task = task
        self.task_group = task_group
        self.function = function
        self._input = input
        self._input_type = {}
        self._input_generators = {}
        self.parameters = {}
        self._form = form
        self._api_protocol = api_protocol
        self._is_binary_input = is_binary_input
        self.resources = None

        if api_protocol in [ApiProtocol.HTTP, ApiProtocol.HTTPS]:
            self._input_resolver = InputResolver(input_instance=self._input)
        else:
            self._input_resolver = InputResolver(input_instance=self._input,
                                                 is_encode_binary=False)

    def add_parameters(self, **params):
        for key, value in params.items():
            self.parameters[key] = value

    def add_resources(self, resources):
        self.resources = resources

    def to_request_object(self) -> str:
        """Convert data to json, called from http request.
        Returns:
            str: Json string.
        """
        self.input = next(self._input_resolver)
        o = {
            k: v
            for k, v in self.__dict__.items()
            if not (k.startswith('_') or k.startswith('task')
                    or k.startswith('function') or v is None)
        }
        return o

    def get_aiohttp_payload(self):
        """Get http payload.
        If there are form, return form data, otherwise
            return input and parameter body.

        Returns:
            is_form, data: if there are are form, is_form is true.
        """
        data = self.to_request_object()
        if self._form is not None:
            form = aiohttp.FormData()
            for key, value in self._form.items():
                form.add_field(key, value)
            form.add_field('model', data['model'])
            if 'input' in data:
                form.add_field('input', json.dumps(data['input']))
            form.add_field('parameters', json.dumps(data['parameters']))
            return True, form()
            """
            mp_writer = aiohttp.MultipartWriter('mixed')
            mp_writer.append('model=%s'%self.model)
            mp_writer.append('input=%s' % json.dumps(self._input))
            mp_writer.append('parameters=%s'%json.dumps(self.parameters))
            mp_writer.append(form())
            return True, mp_writer
            """
        else:
            return False, data

    def get_http_payload(self):
        """Get http payload.
        If there are form, return form data, otherwise
            return input and parameter body.

        Returns:
            is_form, data: if there are are form, is_form is true.
        """
        data = self.to_request_object()
        if self._form is not None:
            return True, self._form, data
        else:
            return False, None, data

    def get_websocket_start_data(self):
        """Process websocket start data.
        If the input data is str, can carry the data in start action package,
        otherwise only parameters.
        Current, only one binary input is supported.
        Return: is_binary, start_package
        """
        if self._is_binary_input:
            return self._only_parameters()
        else:
            for content in self._input_resolver:
                self.input = content
                break

        data = {
            k: v
            for k, v in self.__dict__.items()
            if not (k.startswith('_') or v is None)
        }
        return data

    def get_websocket_continue_data(self):
        for content in self._input_resolver:
            yield content

    def _to_json_only_data(self) -> str:
        o = {
            k: v
            for k, v in self.__dict__.items()
            if not (k.startswith('_') or k.startswith('param'))
        }
        return json.dumps(o, default=lambda o: o.__dict__)

    def get_batch_binary_data(self) -> bytes:
        """Get binary data. used in streaming mode none and
           out (input is not streaming), we send data in one package.
           In this case only has one field input.

        Returns:
            bytes: The binary content, such as audio,image,video file content.
        """
        for content in self._input_resolver:
            return content

    def _only_parameters(self) -> str:
        obj = {'model': self.model, 'parameters': self.parameters, 'input': {}}
        if self.task is not None:
            obj['task'] = self.task
        if self.task_group is not None:
            obj['task_group'] = self.task_group
        if self.function is not None:
            obj['function'] = self.function
        if self.resources is not None:
            obj['resources'] = self.resources
        return obj

    def to_query_parameters(self) -> str:
        query_string = '?'
        for key, value in self.parameters.items:
            param = '%s/%s&' % (key, value)
            query_string += param
        query_string = query_string[0:-1]  # remove last #
        return urlencode(query_string)
