import time

from opentelemetry import context as context_api
from opentelemetry.instrumentation.openai import is_openai_v1
from opentelemetry.instrumentation.openai.shared import (
    _get_openai_base_url,
    metric_shared_attributes,
    model_as_dict,
)
from opentelemetry.instrumentation.openai.utils import (
    _with_image_gen_metric_wrapper,
)
from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY
from opentelemetry.metrics import Counter, Histogram
from opentelemetry.semconv_ai import SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY


@_with_image_gen_metric_wrapper
def image_gen_metrics_wrapper(
    duration_histogram: Histogram,
    exception_counter: Counter,
    wrapped,
    instance,
    args,
    kwargs,
):
    if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY) or context_api.get_value(
        SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY
    ):
        return wrapped(*args, **kwargs)

    try:
        # record time for duration
        start_time = time.time()
        response = wrapped(*args, **kwargs)
        end_time = time.time()
    except Exception as e:  # pylint: disable=broad-except
        end_time = time.time()
        duration = end_time - start_time if "start_time" in locals() else 0

        attributes = {
            "error.type": e.__class__.__name__,
        }

        if duration > 0 and duration_histogram:
            duration_histogram.record(duration, attributes=attributes)
        if exception_counter:
            exception_counter.add(1, attributes=attributes)

        raise e

    if is_openai_v1():
        response_dict = model_as_dict(response)
    else:
        response_dict = response

    # not provide response.model in ImagesResponse response, use model in request kwargs
    shared_attributes = metric_shared_attributes(
        response_model=kwargs.get("model") or None,
        operation="image_gen",
        server_address=_get_openai_base_url(instance),
    )

    duration = end_time - start_time
    if duration_histogram:
        duration_histogram.record(duration, attributes=shared_attributes)

    return response
