from tradingagents.dataflows.tencent_etf import format_tencent_etf_data


def test_format_tencent_etf_data() -> None:
    rows = [
        [f"2026-07-{day:02d}", "1.00", str(1 + day / 100), "1.10", "0.90", str(day * 1000)]
        for day in range(1, 22)
    ]

    result = format_tencent_etf_data("588000", rows)

    assert "数据源: 腾讯行情" in result
    assert "2026-07-21" in result
    assert "MA5" in result
    assert '"ATR14"' in result
    assert '"support_20d"' in result
    assert '"resistance_20d"' in result
    assert '"reference_buy_zone"' in result
    assert '"reference_sell_zone"' in result
    assert '"stop_loss_reference"' in result
    assert "588000" in result
