# Copyright (c) Alibaba, Inc. and its affiliates.

import dataclasses
from dataclasses import dataclass
from typing import Any, List

import dashscope


def get_object_type(name: str):
    dashscope_objects = {
        'assistant': dashscope.Assistant,
        'assistant.deleted': dashscope.DeleteResponse,
        'thread.message': dashscope.ThreadMessage,
        'thread.run': dashscope.Run,
        'thread.run.step': dashscope.RunStep,
        'thread.message.file': dashscope.MessageFile,
        'assistant.file': dashscope.AssistantFile,
        'thread': dashscope.Thread,
    }
    return dashscope_objects.get(name, None)


@dataclass(init=False)
class BaseObjectMixin(object):
    __slots__ = ()

    def __init__(self, **kwargs):
        field_type_map = self._get_fields_type()
        for k, v in kwargs.items():
            field = field_type_map.get(k, None)
            if field and v is not None:
                if dataclasses.is_dataclass(field.type):  # process dataclasses
                    self.__setattr__(k, field.type(**v))
                    continue

            if isinstance(v, dict):
                object_name = v.get('object', None)
                if object_name:
                    object_type = get_object_type(object_name)
                    if object_type:
                        self.__setattr__(k, object_type(**v))
                    else:
                        self.__setattr__(k, v)
                else:
                    self.__setattr__(k, v)
            elif isinstance(v, list):
                obj_list = self._init_list_element_recursive(field, v)
                self.__setattr__(k, obj_list)
            else:
                self.__setattr__(k, v)

    def _init_list_element_recursive(self, field, items: list) -> List[Any]:
        obj_list = []
        for item in items:
            if field:
                # current only support List[cls_name],
                # not support List[cls_nam1, cls_name2]
                element_type = field.type.__args__[0]
                if dataclasses.is_dataclass(element_type):
                    obj_list.append(element_type(**item))
                    continue

            if isinstance(item, dict):
                object_name = item.get('object', None)
                if object_name:
                    object_type = get_object_type(object_name)
                    if object_type:
                        obj_list.append(object_type(**item))
                    else:
                        obj_list.append(item)
                else:
                    obj_list.append(item)
            elif isinstance(item, list):
                obj_list.append(self._init_list_element_recursive(item))
            else:
                obj_list.append(item)
        return obj_list

    def _get_fields_type(self):
        field_type_map = {}
        if dataclasses.is_dataclass(self):
            for field in dataclasses.fields(self):
                field_type_map[field.name] = field
        return field_type_map

    def __setitem__(self, __key: Any, __value: Any) -> None:
        return self.__setattr__(__key, __value)

    def __getitem__(self, __key: Any) -> Any:
        return self.__getattribute__(__key)

    def __contains__(self, item):
        return hasattr(self, item)

    def __delitem__(self, key):
        self.__delattr__(key)

    def _recursive_to_str__(self, input_object) -> Any:
        if isinstance(input_object, list):
            output_object = []
            for item in input_object:
                output_object.append(self._recursive_to_str__(item))
            return output_object
        elif dataclasses.is_dataclass(input_object):
            output_object = {}
            for field in dataclasses.fields(input_object):
                if hasattr(input_object, field.name):
                    output_object[field.name] = self._recursive_to_str__(
                        getattr(input_object, field.name))
            return output_object
        else:
            return input_object

    def __str__(self) -> str:
        real_dict = self.__dict__
        self_fields = dataclasses.fields(self)
        for field in self_fields:
            if hasattr(self, field.name):
                real_dict[field.name] = getattr(self, field.name)
        output_object = {}
        for key, value in real_dict.items():
            output_object[key] = self._recursive_to_str__(value)
        return str(output_object)


@dataclass(init=False)
class BaseList(BaseObjectMixin):
    status_code: int
    has_more: bool
    last_id: str
    first_id: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
