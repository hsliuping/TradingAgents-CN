# Copyright (c) Alibaba, Inc. and its affiliates.

import os
from typing import List

from dashscope.common.error import UnsupportedModel
from dashscope.tokenizers.qwen_tokenizer import QwenTokenizer

from .tokenizer_base import Tokenizer

QWEN_SERIALS = ['qwen-7b-chat', 'qwen-turbo', 'qwen-plus', 'qwen-max']
current_path = os.path.dirname(os.path.abspath(__file__))
root_path = os.path.dirname(current_path)


def get_tokenizer(model: str) -> Tokenizer:
    """Get a tokenizer based on model name.

    Args:
        model (str): The model name.

    Raises:
        UnsupportedModel: Not support model

    Returns:
        Tokenizer: The  `Tokenizer` of the model.
    """
    if model in QWEN_SERIALS:
        return QwenTokenizer(
            os.path.join(root_path, 'resources', 'qwen.tiktoken'))
    elif model.startswith('qwen'):
        return QwenTokenizer(
            os.path.join(root_path, 'resources', 'qwen.tiktoken'))
    else:
        raise UnsupportedModel(
            f'Not support model: {model}, currently only support qwen models.')


def list_tokenizers() -> List[str]:
    """List support models

    Returns:
        List[str]: The model list.
    """
    return QWEN_SERIALS
