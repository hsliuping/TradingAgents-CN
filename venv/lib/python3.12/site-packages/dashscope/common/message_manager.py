# Copyright (c) Alibaba, Inc. and its affiliates.

from collections import deque
from typing import List

from dashscope.api_entities.dashscope_response import (ConversationResponse,
                                                       GenerationResponse,
                                                       Message)


class MessageManager(object):
    DEFAULT_MAXIMUM_MESSAGES = 100

    def __init__(self, max_length: int = None):
        if max_length is None:
            self._dq = deque(maxlen=MessageManager.DEFAULT_MAXIMUM_MESSAGES)
        else:
            self._dq = deque(maxlen=max_length)

    def add_generation_response(self, response: GenerationResponse):
        self._dq.append(Message.from_generation_response(response))

    def add_conversation_response(self, response: ConversationResponse):
        self._dq.append(Message.from_conversation_response(response))

    def add(self, message: Message):
        """Add message to message manager

        Args:
            message (Message): The message to add.
        """
        self._dq.append(message)

    def get(self) -> List[Message]:
        return list(self._dq)
