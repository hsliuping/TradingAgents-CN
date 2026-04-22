from unittest.mock import Mock


def test_index_cache_identity_keeps_requested_and_effective_dates_separate(monkeypatch):
    from core.agents.adapters import index_analyst_v2 as module

    monkeypatch.setattr(module, "apply_stable_data_cutoff", lambda date_str, cutoff_hour=19: "2026-04-20")

    symbol, trade_date, effective_date = module._build_index_cache_identity("2026-04-21")

    assert trade_date == "2026-04-21"
    assert effective_date == "2026-04-20"
    assert symbol == "market_v2__req_20260421__eff_20260420"


def test_get_cached_index_report_uses_effective_date_in_cache_symbol(monkeypatch):
    from core.agents.adapters import index_analyst_v2 as module

    cache = Mock()
    cache.find_cached_analysis_report.return_value = None

    monkeypatch.setattr(module, "_get_cache_manager", lambda: cache)
    monkeypatch.setattr(module, "apply_stable_data_cutoff", lambda date_str, cutoff_hour=19: "2026-04-20")

    module._get_cached_index_report("2026-04-21")

    cache.find_cached_analysis_report.assert_called_once_with(
        report_type="index_report",
        symbol="market_v2__req_20260421__eff_20260420",
        trade_date="2026-04-21",
        max_age_hours=1,
    )


def test_save_index_report_to_cache_uses_effective_date_in_cache_symbol(monkeypatch):
    from core.agents.adapters import index_analyst_v2 as module

    cache = Mock()
    monkeypatch.setattr(module, "_get_cache_manager", lambda: cache)
    monkeypatch.setattr(module, "apply_stable_data_cutoff", lambda date_str, cutoff_hour=19: "2026-04-20")

    saved = module._save_index_report_to_cache("2026-04-21", "x" * 120)

    assert saved is True
    cache.save_analysis_report.assert_called_once_with(
        report_type="index_report",
        report_data="x" * 120,
        symbol="market_v2__req_20260421__eff_20260420",
        trade_date="2026-04-21",
    )