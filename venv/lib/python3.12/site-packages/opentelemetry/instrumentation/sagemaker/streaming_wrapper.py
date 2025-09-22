from opentelemetry.instrumentation.sagemaker.utils import dont_throw
from wrapt import ObjectProxy


class StreamingWrapper(ObjectProxy):
    def __init__(
        self,
        response,
        stream_done_callback=None,
    ):
        super().__init__(response)

        self._stream_done_callback = stream_done_callback
        self._accumulating_body = ""

    def __iter__(self):
        for event in self.__wrapped__:
            self._process_event(event)
            yield event
        self._stream_done_callback(self._accumulating_body)

    @dont_throw
    def _process_event(self, event):
        payload_part = event.get("PayloadPart")
        if not payload_part:
            return

        decoded_payload_part = payload_part.get("Bytes").decode()
        self._accumulating_body += decoded_payload_part
