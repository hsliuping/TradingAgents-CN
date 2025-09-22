from __future__ import annotations

import concurrent.futures as cf
import copy
import functools
import io
import logging
import sys
import threading
import time
import weakref
from multiprocessing import cpu_count
from queue import Empty, Queue
from typing import (
    TYPE_CHECKING,
    Optional,
    Union,
    cast,
)

from langsmith import schemas as ls_schemas
from langsmith import utils as ls_utils
from langsmith._internal._compressed_traces import CompressedTraces
from langsmith._internal._constants import (
    _AUTO_SCALE_DOWN_NEMPTY_TRIGGER,
    _AUTO_SCALE_UP_NTHREADS_LIMIT,
    _AUTO_SCALE_UP_QSIZE_TRIGGER,
    _BOUNDARY,
)
from langsmith._internal._operations import (
    SerializedFeedbackOperation,
    SerializedRunOperation,
    combine_serialized_queue_operations,
)

if TYPE_CHECKING:
    from opentelemetry.context.context import Context  # type: ignore[import]

    from langsmith.client import Client

logger = logging.getLogger("langsmith.client")

HTTP_REQUEST_THREAD_POOL = cf.ThreadPoolExecutor(max_workers=cpu_count() * 3)


@functools.total_ordering
class TracingQueueItem:
    """An item in the tracing queue.

    Attributes:
        priority (str): The priority of the item.
        item (Any): The item itself.
        otel_context (Optional[Context]): The OTEL context of the item.
    """

    priority: str
    item: Union[SerializedRunOperation, SerializedFeedbackOperation]
    otel_context: Optional[Context]

    __slots__ = ("priority", "item", "otel_context")

    def __init__(
        self,
        priority: str,
        item: Union[SerializedRunOperation, SerializedFeedbackOperation],
        otel_context: Optional[Context] = None,
    ) -> None:
        self.priority = priority
        self.item = item
        self.otel_context = otel_context

    def __lt__(self, other: TracingQueueItem) -> bool:
        return (self.priority, self.item.__class__) < (
            other.priority,
            other.item.__class__,
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TracingQueueItem) and (
            self.priority,
            self.item.__class__,
        ) == (other.priority, other.item.__class__)


def _tracing_thread_drain_queue(
    tracing_queue: Queue, limit: int = 100, block: bool = True
) -> list[TracingQueueItem]:
    next_batch: list[TracingQueueItem] = []
    try:
        # wait 250ms for the first item, then
        # - drain the queue with a 50ms block timeout
        # - stop draining if we hit the limit
        # shorter drain timeout is used instead of non-blocking calls to
        # avoid creating too many small batches
        if item := tracing_queue.get(block=block, timeout=0.25):
            next_batch.append(item)
        while item := tracing_queue.get(block=block, timeout=0.05):
            next_batch.append(item)
            if limit and len(next_batch) >= limit:
                break
    except Empty:
        pass
    return next_batch


def _tracing_thread_drain_compressed_buffer(
    client: Client, size_limit: int = 100, size_limit_bytes: int | None = 20_971_520
) -> tuple[Optional[io.BytesIO], Optional[tuple[int, int]]]:
    try:
        if client.compressed_traces is None:
            return None, None
        with client.compressed_traces.lock:
            client.compressed_traces.compressor_writer.flush()
            current_size = client.compressed_traces.buffer.tell()

            pre_compressed_size = client.compressed_traces.uncompressed_size

            if size_limit is not None and size_limit <= 0:
                raise ValueError(f"size_limit must be positive; got {size_limit}")
            if size_limit_bytes is not None and size_limit_bytes < 0:
                raise ValueError(
                    f"size_limit_bytes must be nonnegative; got {size_limit_bytes}"
                )

            if (size_limit_bytes is None or current_size < size_limit_bytes) and (
                size_limit is None or client.compressed_traces.trace_count < size_limit
            ):
                return None, None

            # Write final boundary and close compression stream
            client.compressed_traces.compressor_writer.write(
                f"--{_BOUNDARY}--\r\n".encode()
            )
            client.compressed_traces.compressor_writer.close()

            filled_buffer = client.compressed_traces.buffer
            filled_buffer.context = client.compressed_traces._context

            compressed_traces_info = (pre_compressed_size, current_size)

            client.compressed_traces.reset()

        filled_buffer.seek(0)
        return (filled_buffer, compressed_traces_info)
    except Exception:
        logger.error(
            "LangSmith tracing error: Failed to submit trace data.\n"
            "This does not affect your application's runtime.\n"
            "Error details:",
            exc_info=True,
        )
        # exceptions are logged elsewhere, but we need to make sure the
        # background thread continues to run
        return None, None


def _tracing_thread_handle_batch(
    client: Client,
    tracing_queue: Queue,
    batch: list[TracingQueueItem],
    use_multipart: bool,
    mark_task_done: bool = True,
    ops: Optional[
        list[Union[SerializedRunOperation, SerializedFeedbackOperation]]
    ] = None,
) -> None:
    """Handle a batch of tracing queue items by sending them to LangSmith.

    Args:
        client: The LangSmith client to use for sending data.
        tracing_queue: The queue containing tracing items (used for task_done calls).
        batch: List of tracing queue items to process.
        use_multipart: Whether to use multipart endpoint for sending data.
        mark_task_done: Whether to mark queue tasks as done after processing.
            Set to False when called from parallel execution to avoid double counting.
        ops: Pre-combined serialized operations to use instead of combining from batch.
            If None, operations will be combined from the batch items.
    """
    try:
        if ops is None:
            ops = combine_serialized_queue_operations([item.item for item in batch])

        if use_multipart:
            client._multipart_ingest_ops(ops)
        else:
            if any(isinstance(op, SerializedFeedbackOperation) for op in ops):
                logger.warn(
                    "Feedback operations are not supported in non-multipart mode"
                )
                ops = [
                    op for op in ops if not isinstance(op, SerializedFeedbackOperation)
                ]
            client._batch_ingest_run_ops(cast(list[SerializedRunOperation], ops))

    except Exception:
        logger.error(
            "LangSmith tracing error: Failed to submit trace data.\n"
            "This does not affect your application's runtime.\n"
            "Error details:",
            exc_info=True,
        )
    finally:
        if mark_task_done and tracing_queue is not None:
            for _ in batch:
                try:
                    tracing_queue.task_done()
                except ValueError as e:
                    if "task_done() called too many times" in str(e):
                        # This can happen during shutdown when multiple threads
                        # process the same queue items. It's harmless.
                        logger.debug(
                            f"Ignoring harmless task_done error during shutdown: {e}"
                        )
                    else:
                        raise


def _otel_tracing_thread_handle_batch(
    client: Client,
    tracing_queue: Queue,
    batch: list[TracingQueueItem],
    mark_task_done: bool = True,
    ops: Optional[
        list[Union[SerializedRunOperation, SerializedFeedbackOperation]]
    ] = None,
) -> None:
    """Handle a batch of tracing queue items by exporting them to OTEL.

    Args:
        client: The LangSmith client containing the OTEL exporter.
        tracing_queue: The queue containing tracing items (used for task_done calls).
        batch: List of tracing queue items to process.
        mark_task_done: Whether to mark queue tasks as done after processing.
            Set to False when called from parallel execution to avoid double counting.
        ops: Pre-combined serialized operations to use instead of combining from batch.
            If None, operations will be combined from the batch items.
    """
    try:
        if ops is None:
            ops = combine_serialized_queue_operations([item.item for item in batch])

        run_ops = [op for op in ops if isinstance(op, SerializedRunOperation)]
        otel_context_map = {
            item.item.id: item.otel_context
            for item in batch
            if isinstance(item.item, SerializedRunOperation)
        }
        if run_ops:
            if client.otel_exporter is not None:
                client.otel_exporter.export_batch(run_ops, otel_context_map)
            else:
                logger.error(
                    "LangSmith tracing error: Failed to submit OTEL trace data.\n"
                    "This does not affect your application's runtime.\n"
                    "Error details: client.otel_exporter is None"
                )

    except Exception:
        logger.error(
            "OTEL tracing error: Failed to submit trace data.\n"
            "This does not affect your application's runtime.\n"
            "Error details:",
            exc_info=True,
        )
    finally:
        if mark_task_done and tracing_queue is not None:
            for _ in batch:
                try:
                    tracing_queue.task_done()
                except ValueError as e:
                    if "task_done() called too many times" in str(e):
                        # This can happen during shutdown when multiple threads
                        # process the same queue items. It's harmless.
                        logger.debug(
                            f"Ignoring harmless task_done error during shutdown: {e}"
                        )
                    else:
                        raise


def _hybrid_tracing_thread_handle_batch(
    client: Client,
    tracing_queue: Queue,
    batch: list[TracingQueueItem],
    use_multipart: bool,
    mark_task_done: bool = True,
) -> None:
    """Handle a batch of tracing queue items by sending to both both LangSmith and OTEL.

    Args:
        client: The LangSmith client to use for sending data.
        tracing_queue: The queue containing tracing items (used for task_done calls).
        batch: List of tracing queue items to process.
        use_multipart: Whether to use multipart endpoint for LangSmith.
        mark_task_done: Whether to mark queue tasks as done after processing.
            Set to False primarily for testing when items weren't actually queued.
    """
    # Combine operations once to avoid race conditions
    ops = combine_serialized_queue_operations([item.item for item in batch])

    # Create copies for each thread to avoid shared mutation
    langsmith_ops = copy.deepcopy(ops)
    otel_ops = copy.deepcopy(ops)

    try:
        # Use ThreadPoolExecutor for parallel execution
        with cf.ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both tasks
            future_langsmith = executor.submit(
                _tracing_thread_handle_batch,
                client,
                tracing_queue,
                batch,
                use_multipart,
                False,  # Don't mark tasks done - we'll do it once at the end
                langsmith_ops,
            )
            future_otel = executor.submit(
                _otel_tracing_thread_handle_batch,
                client,
                tracing_queue,
                batch,
                False,  # Don't mark tasks done - we'll do it once at the end
                otel_ops,
            )

            # Wait for both to complete
            future_langsmith.result()
            future_otel.result()
    except RuntimeError as e:
        if "cannot schedule new futures after interpreter shutdown" in str(e):
            # During interpreter shutdown, ThreadPoolExecutor is blocked,
            # fall back to sequential processing
            logger.debug(
                "Interpreter shutting down, falling back to sequential processing"
            )
            _tracing_thread_handle_batch(
                client, tracing_queue, batch, use_multipart, False, langsmith_ops
            )
            _otel_tracing_thread_handle_batch(
                client, tracing_queue, batch, False, otel_ops
            )
        else:
            raise

    # Mark all tasks as done once, only if requested
    if mark_task_done and tracing_queue is not None:
        for _ in batch:
            try:
                tracing_queue.task_done()
            except ValueError as e:
                if "task_done() called too many times" in str(e):
                    # This can happen during shutdown when multiple threads
                    # process the same queue items. It's harmless.
                    logger.debug(
                        f"Ignoring harmless task_done error during shutdown: {e}"
                    )
                else:
                    raise


def _is_using_internal_otlp_provider(client: Client) -> bool:
    """Check if client is using LangSmith's internal OTLP provider.

    Returns True if using LangSmith's internal provider, False if user
    provided their own.
    """
    if not hasattr(client, "otel_exporter") or client.otel_exporter is None:
        return False

    try:
        # Use OpenTelemetry's standard API to get the global TracerProvider
        # Check if OTEL is available
        if not ls_utils.is_truish(ls_utils.get_env_var("OTEL_ENABLED")):
            return False

        # Get the global TracerProvider and check its resource attributes
        from opentelemetry import trace  # type: ignore[import]

        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, "resource") and hasattr(
            tracer_provider.resource, "attributes"
        ):
            is_internal = tracer_provider.resource.attributes.get(
                "langsmith.internal_provider", False
            )
            logger.debug(
                f"TracerProvider resource check: "
                f"langsmith.internal_provider={is_internal}"
            )
            return is_internal

        return False
    except Exception as e:
        logger.debug(
            f"Could not determine TracerProvider type: {e}, assuming user-provided"
        )
        return False


def get_size_limit_from_env() -> Optional[int]:
    size_limit_str = ls_utils.get_env_var(
        "BATCH_INGEST_SIZE_LIMIT",
    )
    if size_limit_str is not None:
        try:
            return int(size_limit_str)
        except ValueError:
            logger.warning(
                f"Invalid value for BATCH_INGEST_SIZE_LIMIT: {size_limit_str}, "
                "continuing with default"
            )
    return None


def _ensure_ingest_config(
    info: ls_schemas.LangSmithInfo,
) -> ls_schemas.BatchIngestConfig:
    default_config = ls_schemas.BatchIngestConfig(
        use_multipart_endpoint=False,
        size_limit_bytes=None,  # Note this field is not used here
        size_limit=100,
        scale_up_nthreads_limit=_AUTO_SCALE_UP_NTHREADS_LIMIT,
        scale_up_qsize_trigger=_AUTO_SCALE_UP_QSIZE_TRIGGER,
        scale_down_nempty_trigger=_AUTO_SCALE_DOWN_NEMPTY_TRIGGER,
    )
    if not info:
        return default_config
    try:
        if not info.batch_ingest_config:
            return default_config
        env_size_limit = get_size_limit_from_env()
        if env_size_limit is not None:
            info.batch_ingest_config["size_limit"] = env_size_limit
        return info.batch_ingest_config
    except BaseException:
        return default_config


def get_tracing_mode() -> tuple[bool, bool]:
    """Get the current tracing mode configuration.

    Returns:
        tuple[bool, bool]:
            - hybrid_otel_and_langsmith: True if both OTEL and LangSmith tracing
              are enabled, which is default behavior if OTEL_ENABLED is set to
              true and OTEL_ONLY is not set to true
            - is_otel_only: True if only OTEL tracing is enabled
    """
    otel_enabled = ls_utils.is_truish(ls_utils.get_env_var("OTEL_ENABLED"))
    otel_only = ls_utils.is_truish(ls_utils.get_env_var("OTEL_ONLY"))

    # If OTEL is not enabled, neither mode should be active
    if not otel_enabled:
        return False, False

    hybrid_otel_and_langsmith = not otel_only
    is_otel_only = otel_only

    return hybrid_otel_and_langsmith, is_otel_only


def tracing_control_thread_func(client_ref: weakref.ref[Client]) -> None:
    client = client_ref()
    if client is None:
        return
    tracing_queue = client.tracing_queue
    assert tracing_queue is not None
    batch_ingest_config = _ensure_ingest_config(client.info)
    size_limit: int = batch_ingest_config["size_limit"]
    scale_up_nthreads_limit: int = batch_ingest_config["scale_up_nthreads_limit"]
    scale_up_qsize_trigger: int = batch_ingest_config["scale_up_qsize_trigger"]
    use_multipart = batch_ingest_config.get("use_multipart_endpoint", False)

    sub_threads: list[threading.Thread] = []
    # 1 for this func, 1 for getrefcount, 1 for _get_data_type_cached
    num_known_refs = 3

    # Disable compression if explicitly set or if using OpenTelemetry
    disable_compression = (
        ls_utils.is_truish(ls_utils.get_env_var("DISABLE_RUN_COMPRESSION"))
        or client.otel_exporter is not None
    )
    if not disable_compression and use_multipart:
        if not (client.info.instance_flags or {}).get(
            "zstd_compression_enabled", False
        ):
            logger.warning(
                "Run compression is not enabled. Please update to the latest "
                "version of LangSmith. Falling back to regular multipart ingestion."
            )
        else:
            client._futures = weakref.WeakSet()
            client.compressed_traces = CompressedTraces()
            client._data_available_event = threading.Event()
            threading.Thread(
                target=tracing_control_thread_func_compress_parallel,
                args=(weakref.ref(client),),
            ).start()

            num_known_refs += 1

    def keep_thread_active() -> bool:
        # if `client.cleanup()` was called, stop thread
        if not client or (
            hasattr(client, "_manual_cleanup") and client._manual_cleanup
        ):
            logger.debug("Client is being cleaned up, stopping tracing thread")
            return False
        if not threading.main_thread().is_alive():
            # main thread is dead. should not be active
            logger.debug("Main thread is dead, stopping tracing thread")
            return False

        if hasattr(sys, "getrefcount"):
            # check if client refs count indicates we're the only remaining
            # reference to the client
            should_keep_thread = sys.getrefcount(client) > num_known_refs + len(
                sub_threads
            )
            if not should_keep_thread:
                logger.debug(
                    "Client refs count indicates we're the only remaining reference "
                    "to the client, stopping tracing thread",
                )
            return should_keep_thread
        else:
            # in PyPy, there is no sys.getrefcount attribute
            # for now, keep thread alive
            return True

    # loop until
    while keep_thread_active():
        for thread in sub_threads:
            if not thread.is_alive():
                sub_threads.remove(thread)
        if (
            len(sub_threads) < scale_up_nthreads_limit
            and tracing_queue.qsize() > scale_up_qsize_trigger
        ):
            new_thread = threading.Thread(
                target=_tracing_sub_thread_func,
                args=(weakref.ref(client), use_multipart),
            )
            sub_threads.append(new_thread)
            new_thread.start()

        hybrid_otel_and_langsmith, is_otel_only = get_tracing_mode()
        if next_batch := _tracing_thread_drain_queue(tracing_queue, limit=size_limit):
            if hybrid_otel_and_langsmith:
                # Hybrid mode: both OTEL and LangSmith
                _hybrid_tracing_thread_handle_batch(
                    client, tracing_queue, next_batch, use_multipart
                )
            elif is_otel_only:
                # OTEL-only mode
                _otel_tracing_thread_handle_batch(client, tracing_queue, next_batch)
            else:
                # LangSmith-only mode
                _tracing_thread_handle_batch(
                    client, tracing_queue, next_batch, use_multipart
                )

    # drain the queue on exit - apply same logic
    hybrid_otel_and_langsmith, is_otel_only = get_tracing_mode()
    while next_batch := _tracing_thread_drain_queue(
        tracing_queue, limit=size_limit, block=False
    ):
        if hybrid_otel_and_langsmith:
            # Hybrid mode cleanup
            logger.debug("Hybrid mode cleanup")
            _hybrid_tracing_thread_handle_batch(
                client, tracing_queue, next_batch, use_multipart
            )
        elif is_otel_only:
            # OTEL-only cleanup
            logger.debug("OTEL-only cleanup")
            _otel_tracing_thread_handle_batch(client, tracing_queue, next_batch)
        else:
            # LangSmith-only cleanup
            logger.debug("LangSmith-only cleanup")
            _tracing_thread_handle_batch(
                client, tracing_queue, next_batch, use_multipart
            )
    logger.debug("Tracing control thread is shutting down")


def tracing_control_thread_func_compress_parallel(
    client_ref: weakref.ref[Client], flush_interval: float = 0.5
) -> None:
    client = client_ref()
    if client is None:
        return
    logger.debug("Tracing control thread func compress parallel called")
    if (
        client.compressed_traces is None
        or client._data_available_event is None
        or client._futures is None
    ):
        logger.error(
            "LangSmith tracing error: Required compression attributes not "
            "initialized.\nThis may affect trace submission but does not "
            "impact your application's runtime."
        )
        return

    batch_ingest_config = _ensure_ingest_config(client.info)
    size_limit: int = batch_ingest_config["size_limit"]
    size_limit_bytes = batch_ingest_config.get("size_limit_bytes", 20_971_520)
    # One for this func, one for the parent thread, one for getrefcount,
    # one for _get_data_type_cached
    num_known_refs = 4

    def keep_thread_active() -> bool:
        # if `client.cleanup()` was called, stop thread
        if not client or (
            hasattr(client, "_manual_cleanup") and client._manual_cleanup
        ):
            logger.debug("Client is being cleaned up, stopping compression thread")
            return False
        if not threading.main_thread().is_alive():
            # main thread is dead. should not be active
            logger.debug("Main thread is dead, stopping compression thread")
            return False
        if hasattr(sys, "getrefcount"):
            # check if client refs count indicates we're the only remaining
            # reference to the client
            should_keep_thread = sys.getrefcount(client) > num_known_refs
            if not should_keep_thread:
                logger.debug(
                    "Client refs count indicates we're the only remaining reference "
                    "to the client, stopping compression thread",
                )
            return should_keep_thread
        else:
            # in PyPy, there is no sys.getrefcount attribute
            # for now, keep thread alive
            return True

    last_flush_time = time.monotonic()

    while True:
        triggered = client._data_available_event.wait(timeout=0.05)
        if not keep_thread_active():
            break

        # If data arrived, clear the event and attempt a drain
        if triggered:
            client._data_available_event.clear()

            data_stream, compressed_traces_info = (
                _tracing_thread_drain_compressed_buffer
            )(client, size_limit, size_limit_bytes)
            # If we have data, submit the send request
            if data_stream is not None:
                try:
                    future = HTTP_REQUEST_THREAD_POOL.submit(
                        client._send_compressed_multipart_req,
                        data_stream,
                        compressed_traces_info,
                    )
                    client._futures.add(future)
                except RuntimeError:
                    client._send_compressed_multipart_req(
                        data_stream,
                        compressed_traces_info,
                    )
            last_flush_time = time.monotonic()

        else:
            if (time.monotonic() - last_flush_time) >= flush_interval:
                (
                    data_stream,
                    compressed_traces_info,
                ) = _tracing_thread_drain_compressed_buffer(
                    client, size_limit=1, size_limit_bytes=1
                )
                if data_stream is not None:
                    try:
                        cf.wait(
                            [
                                HTTP_REQUEST_THREAD_POOL.submit(
                                    client._send_compressed_multipart_req,
                                    data_stream,
                                    compressed_traces_info,
                                )
                            ]
                        )
                    except RuntimeError:
                        client._send_compressed_multipart_req(
                            data_stream,
                            compressed_traces_info,
                        )
                last_flush_time = time.monotonic()

    # Drain the buffer on exit (final flush)
    try:
        (
            final_data_stream,
            compressed_traces_info,
        ) = _tracing_thread_drain_compressed_buffer(
            client, size_limit=1, size_limit_bytes=1
        )
        if final_data_stream is not None:
            try:
                cf.wait(
                    [
                        HTTP_REQUEST_THREAD_POOL.submit(
                            client._send_compressed_multipart_req,
                            final_data_stream,
                            compressed_traces_info,
                        )
                    ]
                )
            except RuntimeError:
                client._send_compressed_multipart_req(
                    final_data_stream,
                    compressed_traces_info,
                )

    except Exception:
        logger.error(
            "LangSmith tracing error: Failed during final cleanup.\n"
            "This does not affect your application's runtime.\n"
            "Error details:",
            exc_info=True,
        )
    logger.debug("Compressed traces control thread is shutting down")


def _tracing_sub_thread_func(
    client_ref: weakref.ref[Client],
    use_multipart: bool,
) -> None:
    client = client_ref()
    if client is None:
        return
    try:
        if not client.info:
            return
    except BaseException as e:
        logger.debug("Error in tracing control thread: %s", e)
        return
    tracing_queue = client.tracing_queue
    assert tracing_queue is not None
    batch_ingest_config = _ensure_ingest_config(client.info)
    size_limit = batch_ingest_config.get("size_limit", 100)
    seen_successive_empty_queues = 0

    # loop until
    while (
        # the main thread dies
        threading.main_thread().is_alive()
        # or we've seen the queue empty 4 times in a row
        and seen_successive_empty_queues
        <= batch_ingest_config["scale_down_nempty_trigger"]
    ):
        if next_batch := _tracing_thread_drain_queue(tracing_queue, limit=size_limit):
            seen_successive_empty_queues = 0

            hybrid_otel_and_langsmith, is_otel_only = get_tracing_mode()
            if hybrid_otel_and_langsmith:
                # Hybrid mode: both OTEL and LangSmith
                _hybrid_tracing_thread_handle_batch(
                    client, tracing_queue, next_batch, use_multipart
                )
            elif is_otel_only:
                # OTEL-only mode
                _otel_tracing_thread_handle_batch(client, tracing_queue, next_batch)
            else:
                # LangSmith-only mode
                _tracing_thread_handle_batch(
                    client, tracing_queue, next_batch, use_multipart
                )
        else:
            seen_successive_empty_queues += 1

    # drain the queue on exit - apply same logic
    hybrid_otel_and_langsmith, is_otel_only = get_tracing_mode()
    while next_batch := _tracing_thread_drain_queue(
        tracing_queue, limit=size_limit, block=False
    ):
        if hybrid_otel_and_langsmith:
            # Hybrid mode cleanup
            _hybrid_tracing_thread_handle_batch(
                client, tracing_queue, next_batch, use_multipart
            )
        elif is_otel_only:
            # OTEL-only cleanup
            logger.debug("OTEL-only cleanup")
            _otel_tracing_thread_handle_batch(client, tracing_queue, next_batch)
        else:
            # LangSmith-only cleanup
            logger.debug("LangSmith-only cleanup")
            _tracing_thread_handle_batch(
                client, tracing_queue, next_batch, use_multipart
            )
    logger.debug("Tracing control sub-thread is shutting down")
