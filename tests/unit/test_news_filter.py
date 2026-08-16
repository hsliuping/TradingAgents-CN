#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新闻相关性过滤器单元测试
覆盖 tradingagents/utils/news_filter.py 的评分、过滤、统计与公司映射逻辑
"""

import pytest
import pandas as pd

from tradingagents.utils.news_filter import (
    NewsRelevanceFilter,
    create_news_filter,
    get_company_name,
)


# 基于招商银行 600036 的过滤器实例
FILTER = NewsRelevanceFilter("600036", "招商银行")


# ---------- calculate_relevance_score：相关性评分 ----------

def test_score_company_name_in_title_gets_highest():
    """标题含公司名称、正文含业绩/财报关键词时应得高分"""
    title = "招商银行发布2024年第三季度业绩报告"
    content = "招商银行今日发布第三季度财报，净利润同比增长8%..."
    assert FILTER.calculate_relevance_score(title, content) == 73


def test_score_irrelevant_etf_news_is_zero():
    """标题含 ETF/指数基金等排除词的新闻应被压制为 0 分"""
    title = "上证180ETF指数基金（530280）自带杠铃策略"
    content = "数据显示，上证180指数前十大权重股分别为贵州茅台、招商银行600036..."
    assert FILTER.calculate_relevance_score(title, content) == 0


def test_score_industry_news_is_zero():
    """仅属于行业板块（无公司特有信息）的新闻应被压制为 0 分"""
    title = "银行ETF指数(512730多只成分股上涨"
    content = "银行板块今日表现强势，招商银行、工商银行等多只成分股上涨..."
    assert FILTER.calculate_relevance_score(title, content) == 0


def test_score_is_clamped_between_zero_and_hundred():
    """评分应始终落在 [0, 100] 区间内"""
    title = "ETF指数基金板块跌停"
    content = "基金指数权重股成分股"
    score = FILTER.calculate_relevance_score(title, content)
    assert 0 <= score <= 100


# ---------- filter_news：新闻过滤 ----------

def test_filter_news_keeps_relevant_and_sorts_desc():
    """过滤后应保留达到阈值的新闻，并按相关性评分降序排列"""
    news = pd.DataFrame([
        {"新闻标题": "招商银行发布2024年第三季度业绩报告",
         "新闻内容": "招商银行今日发布第三季度财报"},
        {"新闻标题": "招商银行获高管增持",
         "新闻内容": "招商银行董事长增持公司股份"},
        {"新闻标题": "银行ETF指数多只成分股上涨",
         "新闻内容": "招商银行、工商银行等多只成分股上涨"},
    ])

    out = FILTER.filter_news(news, min_score=30)

    assert len(out) == 2
    assert "relevance_score" in out.columns
    assert out["relevance_score"].tolist() == [88, 73]  # 降序


def test_filter_news_handles_column_name_fallback():
    """应兼容 '标题'/'内容' 列名的输入"""
    news = pd.DataFrame([
        {"标题": "招商银行发布业绩报告", "内容": "招商银行公布季报"},
    ])

    out = FILTER.filter_news(news, min_score=30)

    assert len(out) >= 1


def test_filter_news_empty_dataframe():
    """空 DataFrame 应原样返回，不抛异常"""
    empty = pd.DataFrame()
    out = FILTER.filter_news(empty, min_score=30)
    assert out.empty


# ---------- get_filter_statistics：过滤统计 ----------

def test_get_filter_statistics():
    original = pd.DataFrame({"新闻标题": ["a", "b", "c"], "新闻内容": ["", "", ""]})
    filtered = pd.DataFrame({"relevance_score": [50, 80]})

    stats = FILTER.get_filter_statistics(original, filtered)

    assert stats["original_count"] == 3
    assert stats["filtered_count"] == 2
    assert stats["filter_rate"] == pytest.approx(100 / 3)
    assert stats["avg_score"] == 65
    assert stats["max_score"] == 80
    assert stats["min_score"] == 50


def test_get_filter_statistics_empty():
    """空输入时统计信息应安全返回 0 值"""
    empty = pd.DataFrame()

    stats = FILTER.get_filter_statistics(empty, empty)

    assert stats["original_count"] == 0
    assert stats["filtered_count"] == 0
    assert stats["filter_rate"] == 0
    assert stats["avg_score"] == 0
    assert stats["max_score"] == 0
    assert stats["min_score"] == 0


# ---------- get_company_name / create_news_filter：公司映射 ----------

def test_get_company_name_mapped():
    assert get_company_name("600036") == "招商银行"


def test_get_company_name_ignores_exchange_suffix():
    """带交易所后缀的代码应映射到同一公司名称"""
    assert get_company_name("600036.SH") == "招商银行"


def test_get_company_name_default_fallback():
    """未映射的代码应返回默认名称"""
    assert get_company_name("999999") == "股票999999"


def test_create_news_filter():
    """便捷工厂函数应返回配置正确的过滤器实例"""
    f = create_news_filter("600036")
    assert isinstance(f, NewsRelevanceFilter)
    assert f.stock_code == "600036"
    assert f.company_name == "招商银行"
