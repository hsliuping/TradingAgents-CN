from __future__ import annotations

import collections
import importlib
import json
import logging
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    Type,
    TypedDict,
    Union,
    cast,
)

import google.ai.generativelanguage as glm
import google.ai.generativelanguage_v1beta.types as gapic
import proto  # type: ignore[import]
from langchain_core.tools import BaseTool
from langchain_core.tools import tool as callable_as_lc_tool
from langchain_core.utils.function_calling import (
    FunctionDescription,
    convert_to_openai_tool,
)
from langchain_core.utils.json_schema import dereference_refs
from pydantic import BaseModel
from pydantic.v1 import BaseModel as BaseModelV1
from typing_extensions import NotRequired

logger = logging.getLogger(__name__)


TYPE_ENUM = {
    "string": glm.Type.STRING,
    "number": glm.Type.NUMBER,
    "integer": glm.Type.INTEGER,
    "boolean": glm.Type.BOOLEAN,
    "array": glm.Type.ARRAY,
    "object": glm.Type.OBJECT,
    "null": None,
}

_ALLOWED_SCHEMA_FIELDS = []
_ALLOWED_SCHEMA_FIELDS.extend([f.name for f in gapic.Schema()._pb.DESCRIPTOR.fields])
_ALLOWED_SCHEMA_FIELDS.extend(
    [
        f
        for f in gapic.Schema.to_dict(
            gapic.Schema(), preserving_proto_field_name=False
        ).keys()
    ]
)
_ALLOWED_SCHEMA_FIELDS_SET = set(_ALLOWED_SCHEMA_FIELDS)


# Info: This is a FunctionDeclaration(=fc).
_FunctionDeclarationLike = Union[
    BaseTool, Type[BaseModel], gapic.FunctionDeclaration, Callable, Dict[str, Any]
]
_GoogleSearchRetrievalLike = Union[
    gapic.GoogleSearchRetrieval,
    Dict[str, Any],
]
_GoogleSearchLike = Union[gapic.Tool.GoogleSearch, Dict[str, Any]]
_CodeExecutionLike = Union[gapic.CodeExecution, Dict[str, Any]]


class _ToolDict(TypedDict):
    function_declarations: Sequence[_FunctionDeclarationLike]
    google_search_retrieval: Optional[_GoogleSearchRetrievalLike]
    google_search: NotRequired[_GoogleSearchLike]
    code_execution: NotRequired[_CodeExecutionLike]


# Info: This means one tool=Sequence of FunctionDeclaration
# The dict should be gapic.Tool like. {"function_declarations": [ { "name": ...}.
# OpenAI like dict is not be accepted. {{'type': 'function', 'function': {'name': ...}
_ToolType = Union[gapic.Tool, _ToolDict, _FunctionDeclarationLike]
_ToolsType = Sequence[_ToolType]


def _format_json_schema_to_gapic(schema: Dict[str, Any]) -> Dict[str, Any]:
    converted_schema: Dict[str, Any] = {}
    for key, value in schema.items():
        if key == "definitions":
            continue
        elif key == "items":
            converted_schema["items"] = _format_json_schema_to_gapic(value)
        elif key == "properties":
            converted_schema["properties"] = _get_properties_from_schema(value)
            continue
        elif key == "allOf":
            if len(value) > 1:
                logger.warning(
                    "Only first value for 'allOf' key is supported. "
                    f"Got {len(value)}, ignoring other than first value!"
                )
            return _format_json_schema_to_gapic(value[0])
        elif key in ["type", "_type"]:
            converted_schema["type"] = str(value).upper()
        elif key not in _ALLOWED_SCHEMA_FIELDS_SET:
            logger.warning(f"Key '{key}' is not supported in schema, ignoring")
        else:
            converted_schema[key] = value
    return converted_schema


def _dict_to_gapic_schema(schema: Dict[str, Any]) -> Optional[gapic.Schema]:
    if schema:
        dereferenced_schema = dereference_refs(schema)
        formatted_schema = _format_json_schema_to_gapic(dereferenced_schema)
        json_schema = json.dumps(formatted_schema)
        return gapic.Schema.from_json(json_schema)
    return None


def _format_dict_to_function_declaration(
    tool: Union[FunctionDescription, Dict[str, Any]],
) -> gapic.FunctionDeclaration:
    return gapic.FunctionDeclaration(
        name=tool.get("name") or tool.get("title"),
        description=tool.get("description"),
        parameters=_dict_to_gapic_schema(tool.get("parameters", {})),
    )


# Info: gapic.Tool means function_declarations and proto.Message.
def convert_to_genai_function_declarations(
    tools: _ToolsType,
) -> gapic.Tool:
    if not isinstance(tools, collections.abc.Sequence):
        logger.warning(
            "convert_to_genai_function_declarations expects a Sequence "
            "and not a single tool."
        )
        tools = [tools]
    gapic_tool = gapic.Tool()
    for tool in tools:
        if any(f in gapic_tool for f in ["google_search_retrieval"]):
            raise ValueError(
                "Providing multiple google_search_retrieval"
                " or mixing with function_declarations is not supported"
            )
        if isinstance(tool, (gapic.Tool)):
            rt: gapic.Tool = (
                tool if isinstance(tool, gapic.Tool) else tool._raw_tool  # type: ignore
            )
            if "google_search_retrieval" in rt:
                gapic_tool.google_search_retrieval = rt.google_search_retrieval
            if "function_declarations" in rt:
                gapic_tool.function_declarations.extend(rt.function_declarations)
            if "google_search" in rt:
                gapic_tool.google_search = rt.google_search
        elif isinstance(tool, dict):
            # not _ToolDictLike
            if not any(
                f in tool
                for f in [
                    "function_declarations",
                    "google_search_retrieval",
                    "google_search",
                    "code_execution",
                ]
            ):
                fd = _format_to_gapic_function_declaration(tool)  # type: ignore[arg-type]
                gapic_tool.function_declarations.append(fd)
                continue
            # _ToolDictLike
            tool = cast(_ToolDict, tool)
            if "function_declarations" in tool:
                function_declarations = tool["function_declarations"]
                if not isinstance(
                    tool["function_declarations"], collections.abc.Sequence
                ):
                    raise ValueError(
                        "function_declarations should be a list"
                        f"got '{type(function_declarations)}'"
                    )
                if function_declarations:
                    fds = [
                        _format_to_gapic_function_declaration(fd)
                        for fd in function_declarations
                    ]
                    gapic_tool.function_declarations.extend(fds)
            if "google_search_retrieval" in tool:
                gapic_tool.google_search_retrieval = gapic.GoogleSearchRetrieval(
                    tool["google_search_retrieval"]
                )
            if "google_search" in tool:
                gapic_tool.google_search = gapic.Tool.GoogleSearch(
                    tool["google_search"]
                )
            if "code_execution" in tool:
                gapic_tool.code_execution = gapic.CodeExecution(tool["code_execution"])
        else:
            fd = _format_to_gapic_function_declaration(tool)  # type: ignore[arg-type]
            gapic_tool.function_declarations.append(fd)
    return gapic_tool


def tool_to_dict(tool: gapic.Tool) -> _ToolDict:
    def _traverse_values(raw: Any) -> Any:
        if isinstance(raw, list):
            return [_traverse_values(v) for v in raw]
        if isinstance(raw, dict):
            return {k: _traverse_values(v) for k, v in raw.items()}
        if isinstance(raw, proto.Message):
            return _traverse_values(type(raw).to_dict(raw))
        return raw

    return _traverse_values(type(tool).to_dict(tool))


def _format_to_gapic_function_declaration(
    tool: _FunctionDeclarationLike,
) -> gapic.FunctionDeclaration:
    if isinstance(tool, BaseTool):
        return _format_base_tool_to_function_declaration(tool)
    elif isinstance(tool, type) and is_basemodel_subclass_safe(tool):
        return _convert_pydantic_to_genai_function(tool)
    elif isinstance(tool, dict):
        if all(k in tool for k in ("type", "function")) and tool["type"] == "function":
            function = tool["function"]
        elif (
            all(k in tool for k in ("name", "description")) and "parameters" not in tool
        ):
            function = cast(dict, tool)
        else:
            if (
                "parameters" in tool and tool["parameters"].get("properties")  # type: ignore[index]
            ):
                function = convert_to_openai_tool(cast(dict, tool))["function"]
            else:
                function = cast(dict, tool)
        function["parameters"] = function.get("parameters") or {}
        # Empty 'properties' field not supported.
        if not function["parameters"].get("properties"):
            function["parameters"] = {}
        return _format_dict_to_function_declaration(cast(FunctionDescription, function))
    elif callable(tool):
        return _format_base_tool_to_function_declaration(callable_as_lc_tool()(tool))
    raise ValueError(f"Unsupported tool type {tool}")


def _format_base_tool_to_function_declaration(
    tool: BaseTool,
) -> gapic.FunctionDeclaration:
    if not tool.args_schema:
        return gapic.FunctionDeclaration(
            name=tool.name,
            description=tool.description,
            parameters=gapic.Schema(
                type=gapic.Type.OBJECT,
                properties={
                    "__arg1": gapic.Schema(type=gapic.Type.STRING),
                },
                required=["__arg1"],
            ),
        )

    if isinstance(tool.args_schema, dict):
        schema = tool.args_schema
    elif issubclass(tool.args_schema, BaseModel):
        schema = tool.args_schema.model_json_schema()
    elif issubclass(tool.args_schema, BaseModelV1):
        schema = tool.args_schema.schema()
    else:
        raise NotImplementedError(
            "args_schema must be a Pydantic BaseModel or JSON schema, "
            f"got {tool.args_schema}."
        )
    parameters = _dict_to_gapic_schema(schema)

    return gapic.FunctionDeclaration(
        name=tool.name or schema.get("title"),
        description=tool.description or schema.get("description"),
        parameters=parameters,
    )


def _convert_pydantic_to_genai_function(
    pydantic_model: Type[BaseModel],
    tool_name: Optional[str] = None,
    tool_description: Optional[str] = None,
) -> gapic.FunctionDeclaration:
    if issubclass(pydantic_model, BaseModel):
        schema = pydantic_model.model_json_schema()
    elif issubclass(pydantic_model, BaseModelV1):
        schema = pydantic_model.schema()
    else:
        raise NotImplementedError(
            f"pydantic_model must be a Pydantic BaseModel, got {pydantic_model}"
        )
    schema = dereference_refs(schema)
    schema.pop("definitions", None)
    function_declaration = gapic.FunctionDeclaration(
        name=tool_name if tool_name else schema.get("title"),
        description=tool_description if tool_description else schema.get("description"),
        parameters={
            "properties": _get_properties_from_schema_any(
                schema.get("properties")
            ),  # TODO: use _dict_to_gapic_schema() if possible
            # "items": _get_items_from_schema_any(
            #     schema
            # ),  # TODO: fix it https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/function-calling?hl#schema
            "required": schema.get("required", []),
            "type_": TYPE_ENUM[schema["type"]],
        },
    )
    return function_declaration


def _get_properties_from_schema_any(schema: Any) -> Dict[str, Any]:
    if isinstance(schema, Dict):
        return _get_properties_from_schema(schema)
    return {}


def _get_properties_from_schema(schema: Dict) -> Dict[str, Any]:
    properties = {}
    for k, v in schema.items():
        if not isinstance(k, str):
            logger.warning(f"Key '{k}' is not supported in schema, type={type(k)}")
            continue
        if not isinstance(v, Dict):
            logger.warning(f"Value '{v}' is not supported in schema, ignoring v={v}")
            continue
        properties_item: Dict[str, Union[str, int, Dict, List]] = {}
        if v.get("type") or v.get("anyOf") or v.get("type_"):
            item_type_ = _get_type_from_schema(v)
            properties_item["type_"] = item_type_
            if _is_nullable_schema(v):
                properties_item["nullable"] = True

            # Replace `v` with chosen definition for array / object json types
            any_of_types = v.get("anyOf")
            if any_of_types and item_type_ in [glm.Type.ARRAY, glm.Type.OBJECT]:
                json_type_ = "array" if item_type_ == glm.Type.ARRAY else "object"
                # Use Index -1 for consistency with `_get_nullable_type_from_schema`
                v = [val for val in any_of_types if val.get("type") == json_type_][-1]

        if v.get("enum"):
            properties_item["enum"] = v["enum"]

        description = v.get("description")
        if description and isinstance(description, str):
            properties_item["description"] = description

        if properties_item.get("type_") == glm.Type.ARRAY and v.get("items"):
            properties_item["items"] = _get_items_from_schema_any(v.get("items"))

        if properties_item.get("type_") == glm.Type.OBJECT:
            if (
                v.get("anyOf")
                and isinstance(v["anyOf"], list)
                and isinstance(v["anyOf"][0], dict)
            ):
                v = v["anyOf"][0]
            v_properties = v.get("properties")
            if v_properties:
                properties_item["properties"] = _get_properties_from_schema_any(
                    v_properties
                )
                if isinstance(v_properties, dict):
                    properties_item["required"] = [
                        k for k, v in v_properties.items() if "default" not in v
                    ]
            else:
                # Providing dummy type for object without properties
                properties_item["type_"] = glm.Type.STRING

        if k == "title" and "description" not in properties_item:
            properties_item["description"] = k + " is " + str(v)

        properties[k] = properties_item

    return properties


def _get_items_from_schema_any(schema: Any) -> Dict[str, Any]:
    if isinstance(schema, (dict, list, str)):
        return _get_items_from_schema(schema)
    return {}


def _get_items_from_schema(schema: Union[Dict, List, str]) -> Dict[str, Any]:
    items: Dict = {}
    if isinstance(schema, List):
        for i, v in enumerate(schema):
            items[f"item{i}"] = _get_properties_from_schema_any(v)
    elif isinstance(schema, Dict):
        items["type_"] = _get_type_from_schema(schema)
        if items["type_"] == glm.Type.OBJECT and "properties" in schema:
            items["properties"] = _get_properties_from_schema_any(schema["properties"])
        if items["type_"] == glm.Type.ARRAY and "items" in schema:
            items["items"] = _format_json_schema_to_gapic(schema["items"])
        if "title" in schema or "description" in schema:
            items["description"] = (
                schema.get("description") or schema.get("title") or ""
            )
        if _is_nullable_schema(schema):
            items["nullable"] = True
        if "required" in schema:
            items["required"] = schema["required"]
    else:
        # str
        items["type_"] = _get_type_from_schema({"type": schema})
        if _is_nullable_schema({"type": schema}):
            items["nullable"] = True

    return items


def _get_type_from_schema(schema: Dict[str, Any]) -> int:
    return _get_nullable_type_from_schema(schema) or glm.Type.STRING


def _get_nullable_type_from_schema(schema: Dict[str, Any]) -> Optional[int]:
    if "anyOf" in schema:
        types = [
            _get_nullable_type_from_schema(sub_schema) for sub_schema in schema["anyOf"]
        ]
        types = [t for t in types if t is not None]  # Remove None values
        if types:
            return types[-1]  # TODO: update FunctionDeclaration and pass all types?
        else:
            pass
    elif "type" in schema or "type_" in schema:
        type_ = schema["type"] if "type" in schema else schema["type_"]
        if isinstance(type_, int):
            return type_
        stype = str(schema["type"]) if "type" in schema else str(schema["type_"])
        return TYPE_ENUM.get(stype, glm.Type.STRING)
    else:
        pass
    return glm.Type.STRING  # Default to string if no valid types found


def _is_nullable_schema(schema: Dict[str, Any]) -> bool:
    if "anyOf" in schema:
        types = [
            _get_nullable_type_from_schema(sub_schema) for sub_schema in schema["anyOf"]
        ]
        return any(t is None for t in types)
    elif "type" in schema or "type_" in schema:
        type_ = schema["type"] if "type" in schema else schema["type_"]
        if isinstance(type_, int):
            return False
        stype = str(schema["type"]) if "type" in schema else str(schema["type_"])
        return TYPE_ENUM.get(stype, glm.Type.STRING) is None
    else:
        pass
    return False


_ToolChoiceType = Union[
    dict, List[str], str, Literal["auto", "none", "any"], Literal[True]
]


class _FunctionCallingConfigDict(TypedDict):
    mode: Union[gapic.FunctionCallingConfig.Mode, str]
    allowed_function_names: Optional[List[str]]


class _ToolConfigDict(TypedDict):
    function_calling_config: _FunctionCallingConfigDict


def _tool_choice_to_tool_config(
    tool_choice: _ToolChoiceType,
    all_names: List[str],
) -> _ToolConfigDict:
    allowed_function_names: Optional[List[str]] = None
    if tool_choice is True or tool_choice == "any":
        mode = "ANY"
        allowed_function_names = all_names
    elif tool_choice == "auto":
        mode = "AUTO"
    elif tool_choice == "none":
        mode = "NONE"
    elif isinstance(tool_choice, str):
        mode = "ANY"
        allowed_function_names = [tool_choice]
    elif isinstance(tool_choice, list):
        mode = "ANY"
        allowed_function_names = tool_choice
    elif isinstance(tool_choice, dict):
        if "mode" in tool_choice:
            mode = tool_choice["mode"]
            allowed_function_names = tool_choice.get("allowed_function_names")
        elif "function_calling_config" in tool_choice:
            mode = tool_choice["function_calling_config"]["mode"]
            allowed_function_names = tool_choice["function_calling_config"].get(
                "allowed_function_names"
            )
        else:
            raise ValueError(
                f"Unrecognized tool choice format:\n\n{tool_choice=}\n\nShould match "
                f"Google GenerativeAI ToolConfig or FunctionCallingConfig format."
            )
    else:
        raise ValueError(f"Unrecognized tool choice format:\n\n{tool_choice=}")
    return _ToolConfigDict(
        function_calling_config={
            "mode": mode.upper(),
            "allowed_function_names": allowed_function_names,
        }
    )


def is_basemodel_subclass_safe(tool: Type) -> bool:
    if safe_import("langchain_core.utils.pydantic", "is_basemodel_subclass"):
        from langchain_core.utils.pydantic import (
            is_basemodel_subclass,  # type: ignore[import]
        )

        return is_basemodel_subclass(tool)
    else:
        return issubclass(tool, BaseModel)


def safe_import(module_name: str, attribute_name: str = "") -> bool:
    try:
        module = importlib.import_module(module_name)
        if attribute_name:
            return hasattr(module, attribute_name)
        return True
    except ImportError:
        return False


def replace_defs_in_schema(original_schema: dict, defs: Optional[dict] = None) -> dict:
    """Given an OpenAPI schema with a property '$defs' replaces all occurrences of
    referenced items in the dictionary.

    Args:
        original_schema: Schema generated by `BaseModel.model_schema_json`
        defs: Definitions for recursive calls.

    Returns:
        Schema with refs replaced.
    """

    new_defs = defs or original_schema.get("$defs")

    if new_defs is None or not isinstance(new_defs, dict):
        return original_schema.copy()

    resulting_schema = {}

    for key, value in original_schema.items():
        if key == "$defs":
            continue

        if not isinstance(value, dict):
            resulting_schema[key] = value
        else:
            if "$ref" in value:
                new_value = value.copy()

                path = new_value.pop("$ref")
                def_key = _get_def_key_from_schema_path(path)
                new_item = new_defs.get(def_key)

                assert isinstance(new_item, dict)
                new_value.update(new_item)

                resulting_schema[key] = replace_defs_in_schema(new_value, defs=new_defs)
            else:
                resulting_schema[key] = replace_defs_in_schema(value, defs=new_defs)

    return resulting_schema


def _get_def_key_from_schema_path(schema_path: str) -> str:
    error_message = f"Malformed schema reference path {schema_path}"

    if not isinstance(schema_path, str) or not schema_path.startswith("#/$defs/"):
        raise ValueError(error_message)

    # Schema has to have only one extra level.
    parts = schema_path.split("/")
    if len(parts) != 3:
        raise ValueError(error_message)

    return parts[-1]
