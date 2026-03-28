import pandas as pd
import pytest

from tradingagents.utils.enhanced_news_filter import create_enhanced_news_filter
from tradingagents.utils.news_filter import create_news_filter
from tradingagents.utils.news_filter_integration import apply_news_filtering_patches


def test_basic_news_filter_keeps_direct_company_news() -> None:
    news_filter = create_news_filter("600036")
    news_df = pd.DataFrame(
        [
            {
                "新闻标题": "招商银行发布2024年第三季度业绩报告",
                "新闻内容": "招商银行今日发布第三季度财报，净利润同比增长8%。",
            },
            {
                "新闻标题": "上证180ETF指数基金自带杠铃策略",
                "新闻内容": "该ETF重仓股包括招商银行600036、贵州茅台等。",
            },
        ]
    )

    filtered = news_filter.filter_news(news_df, min_score=30)

    assert len(filtered) == 1
    assert filtered.iloc[0]["新闻标题"] == "招商银行发布2024年第三季度业绩报告"
    assert filtered.iloc[0]["relevance_score"] >= 30


def test_enhanced_news_filter_returns_weighted_scores_without_optional_models() -> None:
    enhanced_filter = create_enhanced_news_filter(
        "600036",
        use_semantic=False,
        use_local_model=False,
    )
    news_df = pd.DataFrame(
        [
            {
                "新闻标题": "招商银行股东大会通过分红方案",
                "新闻内容": "招商银行股东大会审议通过2024年度利润分配方案。",
            },
            {
                "新闻标题": "银行ETF指数多只成分股上涨",
                "新闻内容": "银行板块今日表现强势，招商银行等成分股上涨。",
            },
        ]
    )

    filtered = enhanced_filter.filter_news_enhanced(news_df, min_score=20)

    assert len(filtered) == 1
    record = filtered.iloc[0]
    assert record["新闻标题"] == "招商银行股东大会通过分红方案"
    assert record["final_score"] >= 20
    assert record["rule_score"] >= record["semantic_score"]


def test_news_filter_integration_returns_original_report_for_a_share_when_provider_not_implemented() -> None:
    enhanced_function = apply_news_filtering_patches()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "tradingagents.dataflows.news.realtime_news.get_realtime_stock_news",
            lambda ticker, curr_date, hours_back: f"{ticker}-{curr_date}-{hours_back}-raw-report",
        )

        result = enhanced_function(
            ticker="600036.SH",
            curr_date="2026-03-27",
            enable_filter=True,
            min_score=30,
        )

    assert result == "600036.SH-2026-03-27-6-raw-report"


pytestmark = []


@pytest.mark.integration
def test_real_news_filtering_with_external_provider() -> None:
    pytest.importorskip("akshare")
    pytest.skip("需要真实外部新闻源，默认跳过外部集成测试")
