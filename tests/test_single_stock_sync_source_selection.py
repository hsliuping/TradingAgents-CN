from fastapi import HTTPException

from app.routers.stock_sync import (
    SingleStockSyncRequest,
    _resolve_single_stock_data_sources,
)


def build_request(
    *,
    sync_realtime: bool,
    sync_historical: bool = False,
    sync_financial: bool = False,
    sync_basic: bool = False,
    data_source: str = "tushare",
) -> SingleStockSyncRequest:
    return SingleStockSyncRequest(
        symbol="600519",
        sync_realtime=sync_realtime,
        sync_historical=sync_historical,
        sync_financial=sync_financial,
        sync_basic=sync_basic,
        data_source=data_source,
        days=365,
    )


def test_realtime_only_requires_akshare() -> None:
    request = build_request(sync_realtime=True, data_source="akshare")

    resolved = _resolve_single_stock_data_sources(request)

    assert resolved == {"realtime": "akshare", "non_realtime": None}


def test_realtime_only_rejects_tushare() -> None:
    request = build_request(sync_realtime=True, data_source="tushare")

    try:
        _resolve_single_stock_data_sources(request)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "仅支持 AKShare" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException")


def test_non_realtime_allows_tushare_and_akshare() -> None:
    tushare_request = build_request(sync_realtime=False, sync_historical=True, data_source="tushare")
    akshare_request = build_request(sync_realtime=False, sync_historical=True, data_source="akshare")

    assert _resolve_single_stock_data_sources(tushare_request) == {
        "realtime": None,
        "non_realtime": "tushare",
    }
    assert _resolve_single_stock_data_sources(akshare_request) == {
        "realtime": None,
        "non_realtime": "akshare",
    }


def test_non_realtime_rejects_mixed() -> None:
    request = build_request(sync_realtime=False, sync_historical=True, data_source="mixed")

    try:
        _resolve_single_stock_data_sources(request)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "mixed" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException")


def test_mixed_mode_routes_realtime_to_akshare_and_others_to_tushare() -> None:
    request = build_request(
        sync_realtime=True,
        sync_historical=True,
        sync_financial=True,
        data_source="mixed",
    )

    resolved = _resolve_single_stock_data_sources(request)

    assert resolved == {"realtime": "akshare", "non_realtime": "tushare"}


def test_combined_mode_can_keep_everything_on_akshare() -> None:
    request = build_request(
        sync_realtime=True,
        sync_historical=True,
        sync_basic=True,
        data_source="akshare",
    )

    resolved = _resolve_single_stock_data_sources(request)

    assert resolved == {"realtime": "akshare", "non_realtime": "akshare"}


def test_combined_mode_rejects_tushare_selection() -> None:
    request = build_request(
        sync_realtime=True,
        sync_historical=True,
        data_source="tushare",
    )

    try:
        _resolve_single_stock_data_sources(request)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "AKShare" in str(exc.detail)
        assert "Tushare" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException")
