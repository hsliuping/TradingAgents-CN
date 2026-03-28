"""Finnhub 本地数据读取与错误提示的单元测试。"""

import json

from tradingagents.dataflows import interface
from tradingagents.dataflows.providers.us.finnhub import get_data_in_range


def test_get_data_in_range_returns_matching_dates(tmp_path):
    news_dir = tmp_path / "finnhub_data" / "news_data"
    news_dir.mkdir(parents=True)

    payload = {
        "2025-01-01": [{"headline": "old", "summary": "ignore"}],
        "2025-01-02": [{"headline": "target", "summary": "keep"}],
        "2025-01-03": [],
        "2025-01-04": [{"headline": "new", "summary": "ignore"}],
    }
    (news_dir / "AAPL_data_formatted.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    result = get_data_in_range(
        ticker="AAPL",
        start_date="2025-01-02",
        end_date="2025-01-03",
        data_type="news_data",
        data_dir=str(tmp_path),
    )

    assert result == {"2025-01-02": [{"headline": "target", "summary": "keep"}]}


def test_get_data_in_range_returns_empty_for_missing_file(tmp_path):
    result = get_data_in_range(
        ticker="MISSING",
        start_date="2025-01-01",
        end_date="2025-01-02",
        data_type="news_data",
        data_dir=str(tmp_path),
    )

    assert result == {}


def test_get_finnhub_news_formats_result(monkeypatch, tmp_path):
    news_dir = tmp_path / "finnhub_data" / "news_data"
    news_dir.mkdir(parents=True)

    payload = {
        "2025-01-01": [{"headline": "Apple Launch", "summary": "New product line."}],
        "2025-01-02": [{"headline": "Apple Earnings", "summary": "Quarterly update."}],
    }
    (news_dir / "AAPL_data_formatted.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(interface, "DATA_DIR", str(tmp_path))

    result = interface.get_finnhub_news("AAPL", "2025-01-02", 1)

    assert "## AAPL News, from 2025-01-01 to 2025-01-02:" in result
    assert "### Apple Launch (2025-01-01)" in result
    assert "Quarterly update." in result


def test_get_finnhub_news_returns_readable_error(monkeypatch, tmp_path):
    monkeypatch.setattr(interface, "DATA_DIR", str(tmp_path))

    result = interface.get_finnhub_news("NONEXISTENT", "2025-01-02", 7)

    assert "无法获取NONEXISTENT的新闻数据" in result
    assert "数据文件不存在或路径配置错误" in result
