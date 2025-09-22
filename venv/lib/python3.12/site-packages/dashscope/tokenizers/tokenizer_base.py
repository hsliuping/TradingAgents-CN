# Copyright (c) Alibaba, Inc. and its affiliates.

from typing import List


class Tokenizer:
    """Base tokenizer interface for local tokenizers.
    """
    def __init__(self):
        pass

    def encode(self, text: str, **kwargs) -> List[int]:
        """Encode input text string to token ids.

        Args:
            text (str): The string to be encoded.

        Returns:
            List[int]: The token ids.
        """
        pass

    def decode(self, token_ids: List[int], **kwargs) -> str:
        """Decode token ids to string.

        Args:
            token_ids (List[int]): The input token ids.

        Returns:
            str: The string of the token ids.
        """
        pass
