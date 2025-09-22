import io
import threading

from zstandard import ZstdCompressor  # type: ignore[import]

from langsmith import utils as ls_utils

compression_level = ls_utils.get_env_var("RUN_COMPRESSION_LEVEL", 1)


class CompressedTraces:
    def __init__(self):
        self.buffer = io.BytesIO()
        self.trace_count = 0
        self.lock = threading.Lock()
        self.uncompressed_size = 0
        self._context = []

        self.compressor_writer = ZstdCompressor(
            level=compression_level, threads=-1
        ).stream_writer(self.buffer, closefd=False)

    def reset(self):
        self.buffer = io.BytesIO()
        self.trace_count = 0
        self.uncompressed_size = 0
        self._context = []
        self.compressor_writer = ZstdCompressor(
            level=compression_level, threads=-1
        ).stream_writer(self.buffer, closefd=False)
