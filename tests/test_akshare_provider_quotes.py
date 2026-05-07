import asyncio
from unittest.mock import Mock, patch

import pandas as pd

from tradingagents.dataflows.providers.china.akshare import AKShareProvider


def test_get_stock_quotes_handles_dash_placeholder_values():
    with patch.object(AKShareProvider, "_initialize_akshare", return_value=None):
        provider = AKShareProvider()

    provider.connected = True
    provider.ak = Mock()
    provider.ak.stock_bid_ask_em = Mock(return_value=pd.DataFrame([
        {"item": "最新", "value": 432.93},
        {"item": "涨幅", "value": 1.23},
        {"item": "涨跌", "value": 5.26},
        {"item": "总手", "value": "-"},
        {"item": "金额", "value": "-"},
        {"item": "换手", "value": 0.0},
        {"item": "量比", "value": "-"},
        {"item": "最高", "value": "-"},
        {"item": "最低", "value": "-"},
        {"item": "今开", "value": "-"},
        {"item": "昨收", "value": 427.67},
    ]))

    quotes = asyncio.run(provider.get_stock_quotes("300750"))

    assert quotes is not None
    assert quotes["code"] == "300750"
    assert quotes["price"] == 432.93
    assert quotes["change_percent"] == 1.23
    assert quotes["volume"] == 0
    assert quotes["amount"] == 0.0
    assert quotes["open"] == 0.0
    assert quotes["high"] == 0.0
    assert quotes["low"] == 0.0
    assert quotes["volume_ratio"] == 0.0
    assert quotes["pre_close"] == 427.67