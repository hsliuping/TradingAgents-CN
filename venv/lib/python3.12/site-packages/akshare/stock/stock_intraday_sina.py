#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/2/21 18:00
Desc: 新浪财经-日内分时数据
https://quote.eastmoney.com/f1.html?newcode=0.000001
"""

import math

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm


def stock_intraday_sina(
    symbol: str = "sz000001", date: str = "20240321"
) -> pd.DataFrame:
    """
    新浪财经-日内分时数据
    https://vip.stock.finance.sina.com.cn/quotes_service/view/cn_bill.php?symbol=sz000001
    :param symbol: 股票代码
    :type symbol: str
    :param date: 交易日
    :type date: str
    :return: 分时数据
    :rtype: pandas.DataFrame
    """
    url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_Bill.GetBillListCount"
    params = {
        "symbol": f"{symbol}",
        "num": "60",
        "page": "1",
        "sort": "ticktime",
        "asc": "0",
        "volume": "0",
        "amount": "0",
        "type": "0",
        "day": "-".join([date[:4], date[4:6], date[6:]]),
    }
    headers = {
        "Referer": f"https://vip.stock.finance.sina.com.cn/quotes_service/view/cn_bill.php?symbol={symbol}",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/107.0.0.0 Safari/537.36",
    }
    r = requests.get(url=url, params=params, headers=headers)
    data_json = r.json()
    total_page = math.ceil(int(data_json) / 60)
    url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_Bill.GetBillList"
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(1, total_page + 1), leave=False):
        params.update({"page": page})
        r = requests.get(url=url, params=params, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json)
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.sort_values(by=["ticktime"], inplace=True, ignore_index=True)
    big_df["price"] = pd.to_numeric(big_df["price"], errors="coerce")
    big_df["volume"] = pd.to_numeric(big_df["volume"], errors="coerce")
    big_df["prev_price"] = pd.to_numeric(big_df["prev_price"], errors="coerce")
    return big_df


if __name__ == "__main__":
    stock_intraday_sina_df = stock_intraday_sina(symbol="sz000001", date="20250221")
    print(stock_intraday_sina_df)
