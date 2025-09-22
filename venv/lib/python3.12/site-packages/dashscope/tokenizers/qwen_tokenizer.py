# Copyright (c) Alibaba, Inc. and its affiliates.

import base64
import unicodedata
from typing import Collection, Dict, List, Set, Union

from .tokenizer_base import Tokenizer

PAT_STR = r"""(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"""  # noqa E501
ENDOFTEXT = '<|endoftext|>'
IMSTART = '<|im_start|>'
IMEND = '<|im_end|>'
# as the default behavior is changed to allow special tokens in
# regular texts, the surface forms of special tokens need to be
# as different as possible to minimize the impact
EXTRAS = tuple((f'<|extra_{i}|>' for i in range(205)))
# changed to use actual index to avoid misconfiguration with vocabulary expansion
SPECIAL_START_ID = 151643
SPECIAL_TOKENS = tuple(
    enumerate(
        ((
            ENDOFTEXT,
            IMSTART,
            IMEND,
        ) + EXTRAS),
        start=SPECIAL_START_ID,
    ))
SPECIAL_TOKENS_SET = set(t for i, t in SPECIAL_TOKENS)


class QwenTokenizer(Tokenizer):
    @staticmethod
    def _load_tiktoken_bpe(tiktoken_bpe_file: str) -> Dict[bytes, int]:
        with open(tiktoken_bpe_file, 'rb') as f:
            contents = f.read()
        return {
            base64.b64decode(token): int(rank)
            for token, rank in (line.split() for line in contents.splitlines()
                                if line)
        }

    def __init__(self, vocab_file, errors='replace', extra_vocab_file=None):
        self._errors = errors
        self._vocab_file = vocab_file
        self._extra_vocab_file = extra_vocab_file

        self._mergeable_ranks = QwenTokenizer._load_tiktoken_bpe(
            vocab_file)  # type: Dict[bytes, int]
        self._special_tokens = {
            token: index
            for index, token in SPECIAL_TOKENS
        }

        # try load extra vocab from file
        if extra_vocab_file is not None:
            used_ids = set(self._mergeable_ranks.values()) | set(
                self._special_tokens.values())
            extra_mergeable_ranks = self._load_tiktoken_bpe(extra_vocab_file)
            for token, index in extra_mergeable_ranks.items():
                if token in self._mergeable_ranks:
                    continue
                if index in used_ids:
                    continue
                self._mergeable_ranks[token] = index
            # the index may be sparse after this, but don't worry tiktoken.Encoding will handle this
        import tiktoken
        enc = tiktoken.Encoding(
            'Qwen',
            pat_str=PAT_STR,
            mergeable_ranks=self._mergeable_ranks,
            special_tokens=self._special_tokens,
        )
        assert (
            len(self._mergeable_ranks) +
            len(self._special_tokens) == enc.n_vocab
        ), f'{len(self._mergeable_ranks) + len(self._special_tokens)} != {enc.n_vocab} in encoding'

        self.decoder = {v: k
                        for k, v in self._mergeable_ranks.items()
                        }  # type: dict[int, bytes|str]
        self.decoder.update({v: k for k, v in self._special_tokens.items()})

        self._tokenizer = enc  # type: tiktoken.Encoding

        self.eod_id = self._tokenizer.eot_token
        self.im_start_id = self._special_tokens[IMSTART]
        self.im_end_id = self._special_tokens[IMEND]

    def encode(
        self,
        text: str,
        allowed_special: Union[Set, str] = 'all',
        disallowed_special: Union[Collection, str] = (),
    ) -> Union[List[List], List]:
        text = unicodedata.normalize('NFC', text)
        return self._tokenizer.encode(text,
                                      allowed_special=allowed_special,
                                      disallowed_special=disallowed_special)

    def decode(
        self,
        token_ids: Union[int, List[int]],
        skip_special_tokens: bool = False,
        errors: str = None,
        **kwargs,
    ) -> str:
        if isinstance(token_ids, int):
            token_ids = [token_ids]
        if skip_special_tokens:
            token_ids = [i for i in token_ids if i < self.eod_id]
        return self._tokenizer.decode(token_ids, errors=errors or self._errors)
