import logging
from datetime import datetime, timedelta

from tradingagents.dataflows.cache.integrated import IntegratedCacheManager


def _build_manager(use_adaptive: bool) -> IntegratedCacheManager:
    manager = IntegratedCacheManager.__new__(IntegratedCacheManager)
    manager.use_adaptive = use_adaptive
    manager.logger = logging.getLogger(__name__)
    return manager


def test_find_cached_stock_data_passes_max_age_to_legacy_cache():
    manager = _build_manager(use_adaptive=False)
    captured = {}

    class LegacyCache:
        def find_cached_stock_data(self, **kwargs):
            captured.update(kwargs)
            return "legacy-cache-key"

    manager.legacy_cache = LegacyCache()

    result = manager.find_cached_stock_data(
        symbol="000002.SZ",
        start_date="2026-04-01",
        end_date="2026-04-10",
        data_source="tushare",
        max_age_hours=24,
    )

    assert result == "legacy-cache-key"
    assert captured["symbol"] == "000002.SZ"
    assert captured["data_source"] == "tushare"
    assert captured["max_age_hours"] == 24


def test_find_cacched_stock_data_alias_is_backward_compatible():
    manager = _build_manager(use_adaptive=False)

    class LegacyCache:
        def find_cached_stock_data(self, **kwargs):
            return kwargs["symbol"]

    manager.legacy_cache = LegacyCache()

    result = manager.find_cacched_stock_data(symbol="000002.SZ", max_age_hours=12)

    assert result == "000002.SZ"


def test_find_cached_stock_data_honors_max_age_in_adaptive_mode():
    manager = _build_manager(use_adaptive=True)

    class AdaptiveCache:
        primary_backend = "file"
        fallback_enabled = False

        def find_cached_data(self, **kwargs):
            return "adaptive-cache-key"

        def _load_from_file(self, cache_key):
            assert cache_key == "adaptive-cache-key"
            return {"timestamp": datetime.now() - timedelta(hours=3)}

    manager.adaptive_cache = AdaptiveCache()

    expired = manager.find_cached_stock_data(symbol="000002.SZ", max_age_hours=1)
    fresh = manager.find_cached_stock_data(symbol="000002.SZ", max_age_hours=4)

    assert expired is None
    assert fresh == "adaptive-cache-key"