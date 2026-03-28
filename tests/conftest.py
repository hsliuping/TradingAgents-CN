import os
import sys
import inspect
from pathlib import Path

import pytest

# 将项目根目录加入 sys.path，确保 `import tradingagents` 可用
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def require_env(name: str) -> str:
    """
    获取外部测试所需环境变量；若未配置则跳过测试。
    """
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"{name} 未配置，跳过外部集成测试")
    return value


# 这些历史测试依赖真实本地服务、真实数据库、外部行情/新闻接口或真实 LLM。
# 默认标准套件应保持离线可运行，因此统一视为 integration。
EXTERNAL_TEST_BASENAMES = {
    "akshare_isolated_test.py",
    "final_gemini_test.py",
    "test_000002_valuation.py",
    "test_002027_specific.py",
    "test_300750_final.py",
    "test_agent_utils_tushare_fix.py",
    "test_akshare_alternative.py",
    "test_akshare_amount.py",
    "test_akshare_api.py",
    "test_akshare_code_format.py",
    "test_akshare_debug.py",
    "test_akshare_direct.py",
    "test_akshare_fixed.py",
    "test_akshare_functionality.py",
    "test_akshare_hk.py",
    "test_akshare_hk_apis.py",
    "test_akshare_performance.py",
    "test_akshare_priority.py",
    "test_akshare_priority_clean.py",
    "test_akshare_priority_fix.py",
    "test_all_apis.py",
    "test_amplitude_api.py",
    "test_amount_fix.py",
    "test_analysis.py",
    "test_analysis_result.py",
    "test_analysis_with_apis.py",
    "test_async_analysis.py",
    "test_api_analysis.py",
    "test_api_format.py",
    "test_batch_analysis_planA.py",
    "test_cache_optimization.py",
    "test_cli_fix.py",
    "test_data_sources_comprehensive.py",
    "test_data_sources_simple.py",
    "test_decision_data.py",
    "test_existing_results.py",
    "test_fixed_analysis.py",
    "test_final_verification.py",
    "test_final_verification_with_config.py",
    "test_frontend_display.py",
    "test_frontend_backend_integration.py",
    "test_fundamentals_no_duplicate.py",
    "test_fundamentals_debug.py",
    "test_fundamentals_generation.py",
    "test_full_analysis_debug.py",
    "test_hk_fundamentals_final.py",
    "test_hk_fundamentals_fix.py",
    "test_hk_apis_simple.py",
    "test_hk_improved.py",
    "test_hk_priority.py",
    "test_hk_simple.py",
    "test_hk_simple_improved.py",
    "test_hk_stock_functionality.py",
    "test_improved_hk_utils.py",
    "test_industries_api.py",
    "test_industry_screening_fix.py",
    "test_llm_tool_calling_comparison.py",
    "test_llm_technical_analysis_debug.py",
    "test_login_api.py",
    "test_level3_deadlock_debug.py",
    "test_level3_fix.py",
    "test_market_analyst_fix.py",
    "test_middleware.py",
    "test_mongodb_save.py",
    "test_model_config.py",
    "test_non_blocking.py",
    "test_news_analyst_integration.py",
    "test_optimized_fundamentals.py",
    "test_optimized_fundamentals_simple.py",
    "test_performance_comparison.py",
    "test_progress_steps.py",
    "test_quick_async.py",
    "test_quick_fix.py",
    "test_raw_data_display.py",
    "test_real_data_levels.py",
    "test_real_estate_api.py",
    "test_reports_api.py",
    "test_reports_fix.py",
    "test_screening_fix.py",
    "test_simple_depth_check.py",
    "test_simple_fundamentals.py",
    "test_signal_processor_debug.py",
    "test_summary_recommendation.py",
    "simple_akshare_test.py",
    "test_tool_interception.py",
    "test_tool_execution_flow.py",
    "test_tool_removal.py",
    "test_unified_fundamentals.py",
    "test_us_stock_analysis.py",
    "test_valuation_check.py",
    "test_valuation_simple.py",
    "test_web_api_akshare.py",
}

EXTERNAL_SOURCE_ANY_PATTERNS = (
    "localhost:8000",
    "MongoClient(",
    "import akshare as ak",
    "graph.propagate(",
    "llm.invoke(",
    "get_china_stock_data_tushare(",
    "get_tushare_provider()",
)

EXTERNAL_SOURCE_ALL_PATTERNS = (
    ("Toolkit(", 'config["online_tools"] = True'),
    ("Toolkit(", "toolkit.get_stock_fundamentals_unified.invoke"),
)


def pytest_collection_modifyitems(config, items):
    source_cache = {}

    for item in items:
        path = getattr(item, "path", None)
        basename = Path(path).name if path is not None else None
        should_mark_integration = basename in EXTERNAL_TEST_BASENAMES

        if path is not None and not should_mark_integration:
            path_obj = Path(path)
            source_text = source_cache.get(path_obj)
            if source_text is None:
                try:
                    source_text = path_obj.read_text(encoding="utf-8")
                except Exception:
                    source_text = ""
                source_cache[path_obj] = source_text

            if any(pattern in source_text for pattern in EXTERNAL_SOURCE_ANY_PATTERNS):
                should_mark_integration = True
            elif any(all(token in source_text for token in token_group) for token_group in EXTERNAL_SOURCE_ALL_PATTERNS):
                should_mark_integration = True

        if should_mark_integration:
            item.add_marker(pytest.mark.integration)

        obj = getattr(item, "obj", None)
        if obj is not None and inspect.iscoroutinefunction(obj):
            item.add_marker(pytest.mark.anyio)
