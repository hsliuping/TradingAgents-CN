#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/5 18:00
Desc: 外盘期货-历史行情数据-日频率
https://finance.sina.com.cn/money/future/hf.html
"""

from datetime import datetime
from io import StringIO

import pandas as pd
import requests

from akshare.futures.futures_hq_sina import (
    futures_foreign_commodity_subscribe_exchange_symbol,
)


def futures_foreign_hist(symbol: str = "ZSD") -> pd.DataFrame:
    """
    外盘期货-历史行情数据-日频率
    https://finance.sina.com.cn/money/future/hf.html
    :param symbol: 外盘期货代码, 可以通过 ak.futures_foreign_commodity_subscribe_exchange_symbol() 来获取所有品种代码
    :type symbol: str
    :return: 历史行情数据-日频率
    :rtype: pandas.DataFrame
    """
    today = f"{datetime.today().year}_{datetime.today().month}_{datetime.today().day}"
    url = (
        f"https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_S{today}=/"
        f"GlobalFuturesService.getGlobalFuturesDailyKLine"
    )
    params = {
        "symbol": symbol,
        "_": today,
        "source": "web",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_df = pd.read_json(StringIO(data_text[data_text.find("[") : -2]))
    return data_df


def futures_foreign_detail(symbol: str = "ZSD") -> pd.DataFrame:
    """
    foreign futures contract detail data
    :param symbol: futures symbol, you can get it from hf_subscribe_exchange_symbol function
    :type symbol: str
    :return: contract detail
    :rtype: pandas.DataFrame
    """
    url = f"https://finance.sina.com.cn/futures/quotes/{symbol}.shtml"
    r = requests.get(url)
    r.encoding = "gbk"
    data_text = r.text
    data_df = pd.read_html(StringIO(data_text))[6]
    return data_df


if __name__ == "__main__":
    futures_foreign_hist_df = futures_foreign_hist(symbol="ZSD")
    print(futures_foreign_hist_df)

    subscribes = futures_foreign_commodity_subscribe_exchange_symbol()

    for item in subscribes:
        futures_foreign_detail_df = futures_foreign_detail(symbol=item)
        print(futures_foreign_detail_df)
