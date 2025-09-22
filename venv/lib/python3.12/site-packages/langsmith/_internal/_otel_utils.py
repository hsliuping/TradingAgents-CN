from __future__ import annotations

from uuid import UUID


def get_otel_trace_id_from_uuid(uuid_val: UUID) -> int:
    """Get OpenTelemetry trace ID as integer from UUID.

    Args:
        uuid_val: The UUID to convert.

    Returns:
        Integer representation of the trace ID.
    """
    trace_id_hex = uuid_val.hex
    return int(trace_id_hex, 16)


def get_otel_span_id_from_uuid(uuid_val: UUID) -> int:
    """Get OpenTelemetry span ID as integer from UUID.

    Args:
        uuid_val: The UUID to convert.

    Returns:
        Integer representation of the span ID.
    """
    uuid_bytes = uuid_val.bytes
    span_id_bytes = uuid_bytes[:8]
    span_id_hex = span_id_bytes.hex()
    return int(span_id_hex, 16)
