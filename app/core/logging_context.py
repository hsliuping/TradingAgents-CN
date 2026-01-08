import logging
import contextvars

# Shared contextvar for trace id across the whole process
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")


class LoggingContextFilter(logging.Filter):
    """Injects trace_id from contextvars into LogRecord.
    Always sets record.trace_id to a string (default '-') so formatters are safe.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.trace_id = trace_id_var.get()
        except Exception:
            record.trace_id = "-"
        return True

