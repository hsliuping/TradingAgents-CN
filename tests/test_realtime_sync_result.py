from app.services.realtime_sync_result import normalize_realtime_sync_result


def test_empty_provider_result_counts_all_requested_symbols_as_failed():
    """Returning an empty quote map must not be presented as a 0/0 success."""
    result = normalize_realtime_sync_result(
        ["000001", "000002"],
        {
            "success_count": 0,
            "error_count": 0,
            "errors": [{"error": "rt_k permission denied"}],
        },
    )

    assert result["total_processed"] == 2
    assert result["success_count"] == 0
    assert result["error_count"] == 2
    assert result["errors"][0]["error"] == "rt_k permission denied"


def test_provider_error_count_never_exceeds_the_requested_symbol_count():
    result = normalize_realtime_sync_result(
        ["000001", "000002"],
        {"success_count": 1, "error_count": 0, "errors": []},
    )

    assert result["success_count"] == 1
    assert result["error_count"] == 1
