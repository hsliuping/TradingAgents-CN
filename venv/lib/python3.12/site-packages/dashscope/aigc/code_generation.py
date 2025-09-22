# Copyright (c) Alibaba, Inc. and its affiliates.

from typing import Generator, List, Union

from dashscope.api_entities.dashscope_response import (DashScopeAPIResponse,
                                                       DictMixin, Role)
from dashscope.client.base_api import BaseApi
from dashscope.common.constants import MESSAGE, SCENE
from dashscope.common.error import InputRequired, ModelRequired
from dashscope.common.utils import _get_task_group_and_task


class MessageParam(DictMixin):
    role: str

    def __init__(self, role: str, **kwargs):
        super().__init__(role=role, **kwargs)


class UserRoleMessageParam(MessageParam):
    content: str

    def __init__(self, content: str, **kwargs):
        super().__init__(role=Role.USER, content=content, **kwargs)


class AttachmentRoleMessageParam(MessageParam):
    meta: dict

    def __init__(self, meta: dict, **kwargs):
        super().__init__(role=Role.ATTACHMENT, meta=meta, **kwargs)


class OtherRoleContentMessageParam(MessageParam):
    content: str

    def __init__(self, role: str, content: str, **kwargs):
        super().__init__(role=role, content=content, **kwargs)


class OtherRoleMetaMessageParam(MessageParam):
    meta: dict

    def __init__(self, role: str, meta: dict, **kwargs):
        super().__init__(role=role, meta=meta, **kwargs)


class CodeGeneration(BaseApi):
    function = 'generation'
    """API for AI-Generated Content(AIGC) models.

    """
    class Models:
        tongyi_lingma_v1 = 'tongyi-lingma-v1'

    class Scenes:
        custom = 'custom'
        nl2code = 'nl2code'
        code2comment = 'code2comment'
        code2explain = 'code2explain'
        commit2msg = 'commit2msg'
        unit_test = 'unittest'
        code_qa = 'codeqa'
        nl2sql = 'nl2sql'

    @classmethod
    def call(
        cls,
        model: str,
        scene: str = None,
        api_key: str = None,
        message: List[MessageParam] = None,
        workspace: str = None,
        **kwargs
    ) -> Union[DashScopeAPIResponse, Generator[DashScopeAPIResponse, None,
                                               None]]:
        """Call generation model service.

        Args:
            model (str): The requested model, such as tongyi-lingma-v1
            scene (str): Scene type, single choice, such as custom
                examples:
                    custom：User defined prompt
                    nl2code：Natural language generated code
                    code2comment：annotation
                    code2explain：explain
                    commit2msg：Automatically generate commit
                    uinttest：Generating Unit Tests
                    codeqa：Code Q&A
                    nl2sql：Generate SQL code using natural language
            api_key (str, optional): The api api_key, can be None,
                if None, will get by default rule(TODO: api key doc).
            message (list): The generation messages.
                scene == custom, examples:
                    [{"role": "user", "content": "根据下面的功能描述生成一个python函数。代码的功能是计算给定路径下所有文件的总大小。"}]  # noqa E501
                scene == nl2code, examples:
                    [{"role": "user", "content": "计算给定路径下所有文件的总大小"}, {"role": "attachment", "meta": {"language": "java"}}]  # noqa E501
                scene == code2comment, examples:
                    [{"role": "user", "content": "1. 生成中文注释\n2. 仅生成代码部分，不需要额外解释函数功能\n"}, {"role": "attachment", "meta": {"code": "\t\t@Override\n\t\tpublic  CancelExportTaskResponse  cancelExportTask(\n\t\t\t\tCancelExportTask  cancelExportTask)  {\n\t\t\tAmazonEC2SkeletonInterface  ec2Service  =  ServiceProvider.getInstance().getServiceImpl(AmazonEC2SkeletonInterface.class);\n\t\t\treturn  ec2Service.cancelExportTask(cancelExportTask);\n\t\t}", "language": "java"}}]  # noqa E501
                scene == code2explain, examples:
                    [{"role": "user", "content": "要求不低于200字"}, {"role": "attachment", "meta": {"code": "@Override\n                                public  int  getHeaderCacheSize()\n                                {\n                                        return  0;\n                                }\n\n", "language": "java"}}]  # noqa E501
                scene == commit2msg, examples:
                    [{"role": "attachment", "meta": {"diff_list": [{"diff": "--- src/com/siondream/core/PlatformResolver.java\n+++ src/com/siondream/core/PlatformResolver.java\n@@ -1,11 +1,8 @@\npackage com.siondream.core;\n-\n-import com.badlogic.gdx.files.FileHandle;\n\npublic interface PlatformResolver {\npublic void openURL(String url);\npublic void rateApp();\npublic void sendFeedback();\n-\tpublic FileHandle[] listFolder(String path);\n}\n", "old_file_path": "src/com/siondream/core/PlatformResolver.java", "new_file_path": "src/com/siondream/core/PlatformResolver.java"}]}}]  # noqa E501
                scene == unittest, examples:
                    [{"role": "attachment", "meta": {"code": "public static <T> TimestampMap<T> parseTimestampMap(Class<T> typeClass, String input, DateTimeZone timeZone) throws IllegalArgumentException {\n        if (typeClass == null) {\n            throw new IllegalArgumentException(\"typeClass required\");\n        }\n\n        if (input == null) {\n            return null;\n        }\n\n        TimestampMap result;\n\n        typeClass = AttributeUtils.getStandardizedType(typeClass);\n        if (typeClass.equals(String.class)) {\n            result = new TimestampStringMap();\n        } else if (typeClass.equals(Byte.class)) {\n            result = new TimestampByteMap();\n        } else if (typeClass.equals(Short.class)) {\n            result = new TimestampShortMap();\n        } else if (typeClass.equals(Integer.class)) {\n            result = new TimestampIntegerMap();\n        } else if (typeClass.equals(Long.class)) {\n            result = new TimestampLongMap();\n        } else if (typeClass.equals(Float.class)) {\n            result = new TimestampFloatMap();\n        } else if (typeClass.equals(Double.class)) {\n            result = new TimestampDoubleMap();\n        } else if (typeClass.equals(Boolean.class)) {\n            result = new TimestampBooleanMap();\n        } else if (typeClass.equals(Character.class)) {\n            result = new TimestampCharMap();\n        } else {\n            throw new IllegalArgumentException(\"Unsupported type \" + typeClass.getClass().getCanonicalName());\n        }\n\n        if (input.equalsIgnoreCase(EMPTY_VALUE)) {\n            return result;\n        }\n\n        StringReader reader = new StringReader(input + ' ');// Add 1 space so\n                                                            // reader.skip\n                                                            // function always\n                                                            // works when\n                                                            // necessary (end of\n                                                            // string not\n                                                            // reached).\n\n        try {\n            int r;\n            char c;\n            while ((r = reader.read()) != -1) {\n                c = (char) r;\n                switch (c) {\n                    case LEFT_BOUND_SQUARE_BRACKET:\n                    case LEFT_BOUND_BRACKET:\n                        parseTimestampAndValue(typeClass, reader, result, timeZone);\n                        break;\n                    default:\n                        // Ignore other chars outside of bounds\n                }\n            }\n        } catch (IOException ex) {\n            throw new RuntimeException(\"Unexpected expection while parsing timestamps\", ex);\n        }\n\n        return result;\n    }", "language": "java"}}]  # noqa E501
                scene == codeqa, examples:
                    [{"role": "user", "content": "I'm writing a small web server in Python, using BaseHTTPServer and a custom subclass of BaseHTTPServer.BaseHTTPRequestHandler. Is it possible to make this listen on more than one port?\nWhat I'm doing now:\nclass MyRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):\n  def doGET\n  [...]\n\nclass ThreadingHTTPServer(ThreadingMixIn, HTTPServer): \n    pass\n\nserver = ThreadingHTTPServer(('localhost', 80), MyRequestHandler)\nserver.serve_forever()"}]  # noqa E501
                scene == nl2sql, examples:
                    [{"role": "user", "content": "小明的总分数是多少"}, {"role": "attachment", "meta": {"synonym_infos": {"学生姓名": "姓名|名字|名称", "学生分数": "分数|得分"}, "recall_infos": [{"content": "student_score.id='小明'", "score": "0.83"}], "schema_infos": [{"table_id": "student_score", "table_desc": "学生分数表", "columns": [{"col_name": "id", "col_caption": "学生id", "col_desc": "例值为:1,2,3", "col_type": "string"}, {"col_name": "name", "col_caption": "学生姓名", "col_desc": "例值为:张三,李四,小明", "col_type": "string"}, {"col_name": "score", "col_caption": "学生分数", "col_desc": "例值为:98,100,66", "col_type": "string"}]}]}}]  # noqa E501
            workspace (str): The dashscope workspace id.
            **kwargs:
                n(int, `optional`): The number of output results, currently only supports 1, with a default value of 1  # noqa E501

        Returns:
            Union[DashScopeAPIResponse,
                  Generator[DashScopeAPIResponse, None, None]]: If
            stream is True, return Generator, otherwise DashScopeAPIResponse.
        """
        if (scene is None or not scene) or (message is None or not message):
            raise InputRequired('scene and message is required!')
        if model is None or not model:
            raise ModelRequired('Model is required!')
        task_group, task = _get_task_group_and_task(__name__)
        input, parameters = cls._build_input_parameters(
            model, scene, message, **kwargs)
        response = super().call(model=model,
                                task_group=task_group,
                                task=task,
                                function=CodeGeneration.function,
                                api_key=api_key,
                                input=input,
                                workspace=workspace,
                                **parameters)

        is_stream = kwargs.get('stream', False)
        if is_stream:
            return (rsp for rsp in response)
        else:
            return response

    @classmethod
    def _build_input_parameters(cls, model, scene, message, **kwargs):
        parameters = {'n': kwargs.pop('n', 1)}
        input = {SCENE: scene, MESSAGE: message}
        return input, {**parameters, **kwargs}
