from tradingagents_indicators import ma, rsi, macd, boll

CLOSES = [10, 11, 12, 11, 13, 14, 13, 15, 16, 15, 17, 18, 17, 19, 20,
          19, 21, 22, 21, 23, 24, 23, 25, 26, 25, 27, 28, 27, 29, 30]


def test_ma_last_equals_mean_of_window():
    assert round(ma(CLOSES, 5)[-1], 4) == round(sum(CLOSES[-5:]) / 5, 4)


def test_ma_short_series_returns_none_prefix():
    out = ma([1, 2, 3], 5)
    assert out[-1] is None and len(out) == 3


def test_rsi_bounds():
    r = rsi(CLOSES, 6)[-1]
    assert 0 <= r <= 100


def test_macd_keys_and_length():
    m = macd(CLOSES)
    assert set(m.keys()) == {"dif", "dea", "hist"}
    assert len(m["dif"]) == len(CLOSES)


def test_boll_upper_ge_mid_ge_lower():
    b = boll(CLOSES, 20)
    assert b["upper"][-1] >= b["mid"][-1] >= b["lower"][-1]
