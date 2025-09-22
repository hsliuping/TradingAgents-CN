# Copyright (c) Alibaba, Inc. and its affiliates.

import os
from typing import Optional

import dashscope
from dashscope.common.constants import (DEFAULT_DASHSCOPE_API_KEY_FILE_PATH,
                                        DEFAULT_DASHSCOPE_CACHE_PATH)
from dashscope.common.error import AuthenticationError


def get_default_api_key():
    if dashscope.api_key is not None:
        # user set environment variable DASHSCOPE_API_KEY
        return dashscope.api_key
    elif dashscope.api_key_file_path:
        # user set environment variable DASHSCOPE_API_KEY_FILE_PATH
        with open(dashscope.api_key_file_path, 'rt',
                  encoding='utf-8') as f:  # open with text mode.
            return f.read().strip()
    else:  # Find the api key from default key file.
        if os.path.exists(DEFAULT_DASHSCOPE_API_KEY_FILE_PATH):
            with open(DEFAULT_DASHSCOPE_API_KEY_FILE_PATH,
                      'rt',
                      encoding='utf-8') as f:
                return f.read().strip()

    raise AuthenticationError(
        'No api key provided. You can set by dashscope.api_key = your_api_key in code, '  # noqa: E501
        'or you can set it via environment variable DASHSCOPE_API_KEY= your_api_key. '  # noqa: E501
        'You can store your api key to a file, and use dashscope.api_key_file_path=api_key_file_path in code, '  # noqa: E501
        'or you can set api key file path via environment variable DASHSCOPE_API_KEY_FILE_PATH, '  # noqa: E501
        'You can call save_api_key to api_key_file_path or default path(~/.dashscope/api_key).'  # noqa: E501
    )


def save_api_key(api_key: str, api_key_file_path: Optional[str] = None):
    if api_key_file_path is None:
        os.makedirs(DEFAULT_DASHSCOPE_CACHE_PATH, exist_ok=True)
        with open(DEFAULT_DASHSCOPE_API_KEY_FILE_PATH, 'w+') as f:
            f.write(api_key)
    else:
        os.makedirs(os.path.dirname(api_key_file_path), exist_ok=True)
        with open(api_key_file_path, 'w+') as f:
            f.write(api_key)
