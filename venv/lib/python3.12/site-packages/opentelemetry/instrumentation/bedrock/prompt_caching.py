from opentelemetry import trace


class CachingHeaders:
    READ = "x-amzn-bedrock-cache-read-input-token-count"
    WRITE = "x-amzn-bedrock-cache-write-input-token-count"


class CacheSpanAttrs:  # TODO: move it under SemConv pkg
    TYPE = "gen_ai.cache.type"
    CACHED = "gen_ai.prompt_caching"


def prompt_caching_handling(headers, vendor, model, metric_params):
    base_attrs = {
        "gen_ai.system": vendor,
        "gen_ai.response.model": model,
    }
    span = trace.get_current_span()
    if CachingHeaders.READ in headers:
        read_cached_tokens = int(headers[CachingHeaders.READ])
        metric_params.prompt_caching.add(
            read_cached_tokens,
            attributes={
                **base_attrs,
                CacheSpanAttrs.TYPE: "read",
            },
        )
        if read_cached_tokens > 0:
            span.set_attribute(CacheSpanAttrs.CACHED, "read")
    if CachingHeaders.WRITE in headers:
        write_cached_tokens = int(headers[CachingHeaders.WRITE])
        metric_params.prompt_caching.add(
            write_cached_tokens,
            attributes={
                **base_attrs,
                CacheSpanAttrs.TYPE: "write",
            },
        )
        if write_cached_tokens > 0:
            span.set_attribute(CacheSpanAttrs.CACHED, "write")
