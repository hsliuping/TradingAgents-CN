from llama_index.core.instrumentation import get_dispatcher

from literalai.client import LiteralClient
from literalai.instrumentation.llamaindex.event_handler import LiteralEventHandler
from literalai.instrumentation.llamaindex.span_handler import LiteralSpanHandler

is_llamaindex_instrumented = False


def instrument_llamaindex(client: "LiteralClient"):
    """
    Instruments LlamaIndex to automatically send logs to Literal AI.
    """
    global is_llamaindex_instrumented
    if is_llamaindex_instrumented:
        return

    root_dispatcher = get_dispatcher()

    span_handler = LiteralSpanHandler()
    root_dispatcher.add_span_handler(span_handler)

    event_handler = LiteralEventHandler(
        literal_client=client, llama_index_span_handler=span_handler
    )
    root_dispatcher.add_event_handler(event_handler)

    is_llamaindex_instrumented = True
