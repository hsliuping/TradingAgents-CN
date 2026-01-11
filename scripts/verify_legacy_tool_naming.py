"""
验证旧版工具的命名一致性

对比：
1. Toolkit 中的方法名
2. legacy_bridge.py 中注册的 tool_id
3. config.py 中定义的工具元数据
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Toolkit 中带 @tool 装饰器的方法（从 agent_utils.py 中提取）
TOOLKIT_METHODS = [
    "get_reddit_news",
    "get_finnhub_news",
    "get_reddit_stock_info",
    "get_chinese_social_sentiment",
    # "get_china_stock_data",  # 已移除 @tool
    "get_china_market_overview",
    "get_YFin_data",
    "get_YFin_data_online",
    "get_stockstats_indicators_report",
    "get_stockstats_indicators_report_online",
    "get_finnhub_company_insider_sentiment",
    "get_finnhub_company_insider_transactions",
    "get_simfin_balance_sheet",
    "get_simfin_cashflow",
    "get_simfin_income_stmt",
    "get_google_news",
    "get_realtime_stock_news",
    "get_stock_news_openai",
    "get_global_news_openai",
    # "get_fundamentals_openai",  # 已移除 @tool
    # "get_china_fundamentals",  # 已移除 @tool
    # "get_hk_stock_data_unified",  # 已移除 @tool
    "get_stock_fundamentals_unified",
    "get_stock_market_data_unified",
    "get_stock_news_unified",
    "get_stock_sentiment_unified",
]

# legacy_bridge.py 中注册的工具 ID
LEGACY_BRIDGE_TOOLS = {
    "get_reddit_news": "get_reddit_news_legacy",
    "get_finnhub_news": "get_finnhub_news_legacy",
    "get_google_news": "get_google_news_legacy",
    "get_realtime_stock_news": "get_realtime_stock_news_legacy",
    "get_stock_news_openai": "get_stock_news_openai_legacy",
    "get_global_news_openai": "get_global_news_openai_legacy",
    "get_reddit_stock_info": "get_reddit_stock_info_legacy",
    "get_chinese_social_sentiment": "get_chinese_social_sentiment_legacy",
    "get_china_market_overview": "get_china_market_overview_legacy",
    "get_stockstats_indicators_report": "get_stockstats_indicators_report_legacy",
    "get_stockstats_indicators_report_online": "get_stockstats_indicators_report_online_legacy",
    "get_YFin_data": "get_yfin_data_legacy",
    "get_YFin_data_online": "get_yfin_data_online_legacy",
    "get_finnhub_company_insider_sentiment": "get_finnhub_company_insider_sentiment_legacy",
    "get_finnhub_company_insider_transactions": "get_finnhub_company_insider_transactions_legacy",
    "get_simfin_income_stmt": "get_simfin_income_stmt_legacy",
    "get_simfin_balance_sheet": "get_simfin_balance_sheet_legacy",
    "get_simfin_cashflow": "get_simfin_cashflow_legacy",
}

# config.py 中定义的工具（旧版，不带 _legacy 后缀）
CONFIG_TOOLS_OLD_STYLE = [
    "get_YFin_data_online",
    "get_YFin_data",
    "get_stockstats_indicators_report_online",
    "get_stockstats_indicators_report",
    "get_finnhub_company_insider_sentiment",
    "get_finnhub_company_insider_transactions",
    "get_simfin_balance_sheet",
    "get_simfin_cashflow",
    "get_simfin_income_stmt",
    "get_global_news_openai",
    "get_google_news",
    "get_finnhub_news",
    "get_reddit_news",
    "get_stock_news_openai",
    "get_reddit_stock_info",
]


def verify_naming():
    """验证命名一致性"""
    
    logger.info("=" * 80)
    logger.info("旧版工具命名一致性验证")
    logger.info("=" * 80)
    
    # 1. 检查 Toolkit 方法是否都在 legacy_bridge 中注册
    logger.info("\n1️⃣ 检查 Toolkit 方法是否都在 legacy_bridge 中注册:")
    logger.info("-" * 80)
    
    missing_in_bridge = []
    for method in TOOLKIT_METHODS:
        if method.startswith("get_stock_") and method.endswith("_unified"):
            # 跳过 v2.0 统一工具
            continue
        
        if method not in LEGACY_BRIDGE_TOOLS:
            missing_in_bridge.append(method)
            logger.warning(f"  ❌ {method} - 未在 legacy_bridge.py 中注册")
        else:
            logger.info(f"  ✅ {method} → {LEGACY_BRIDGE_TOOLS[method]}")
    
    # 2. 检查命名规范
    logger.info("\n2️⃣ 检查 legacy_bridge 中的命名规范:")
    logger.info("-" * 80)
    
    naming_issues = []
    for toolkit_name, bridge_id in LEGACY_BRIDGE_TOOLS.items():
        # 检查是否正确添加了 _legacy 后缀
        expected_id = toolkit_name.lower() + "_legacy"
        
        if bridge_id != expected_id:
            naming_issues.append((toolkit_name, bridge_id, expected_id))
            logger.warning(f"  ⚠️ {toolkit_name}:")
            logger.warning(f"     实际: {bridge_id}")
            logger.warning(f"     期望: {expected_id}")
        else:
            logger.info(f"  ✅ {toolkit_name} → {bridge_id}")
    
    # 3. 检查 config.py 中的旧版工具定义
    logger.info("\n3️⃣ 检查 config.py 中的旧版工具定义:")
    logger.info("-" * 80)
    logger.info("  这些工具应该被删除，因为它们没有实现（只有 legacy 版本）:")
    
    for tool_id in CONFIG_TOOLS_OLD_STYLE:
        logger.warning(f"  ❌ {tool_id} - 应该删除（使用 {tool_id.lower()}_legacy 代替）")
    
    # 总结
    logger.info("\n" + "=" * 80)
    logger.info("📊 总结:")
    logger.info("=" * 80)
    logger.info(f"  - Toolkit 方法总数: {len(TOOLKIT_METHODS)}")
    logger.info(f"  - legacy_bridge 注册总数: {len(LEGACY_BRIDGE_TOOLS)}")
    logger.info(f"  - 未注册的方法: {len(missing_in_bridge)}")
    logger.info(f"  - 命名不规范: {len(naming_issues)}")
    logger.info(f"  - config.py 中应删除的旧版工具: {len(CONFIG_TOOLS_OLD_STYLE)}")
    
    if missing_in_bridge:
        logger.info(f"\n⚠️ 需要在 legacy_bridge.py 中添加以下工具:")
        for method in missing_in_bridge:
            logger.info(f"  - {method}")
    
    if naming_issues:
        logger.info(f"\n⚠️ 需要修正以下命名:")
        for toolkit_name, actual, expected in naming_issues:
            logger.info(f"  - {toolkit_name}: {actual} → {expected}")


if __name__ == "__main__":
    verify_naming()

