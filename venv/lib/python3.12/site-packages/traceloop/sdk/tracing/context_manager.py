from contextlib import contextmanager

from traceloop.sdk.tracing.tracing import TracerWrapper


@contextmanager
def get_tracer(flush_on_exit: bool = False):
    wrapper = TracerWrapper()
    try:
        yield wrapper.get_tracer()
    finally:
        if flush_on_exit:
            wrapper.flush()
