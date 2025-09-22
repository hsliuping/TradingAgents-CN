# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/11/5 16:00
Desc: 雪球-行情中心-沪深股市-内部交易
https://xueqiu.com/hq/insider
"""

import pandas as pd
import requests


def stock_inner_trade_xq() -> pd.DataFrame:
    """
    雪球-行情中心-沪深股市-内部交易
    https://xueqiu.com/hq/insider
    :return: 内部交易
    :rtype: pandas.DataFrame
    """
    url = "https://xueqiu.com/service/v5/stock/f10/cn/skholderchg"
    params = {
        "size": "100000",
        "page": "1",
        "extend": "true",
    }
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Host": "xueqiu.com",
        "Pragma": "no-cache",
        "Referer": "https://xueqiu.com/hq",
        "sec-ch-ua": '" Not A;Brand";v="99", "Chromium";v="100", "Google Chrome";v="100"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/100.0.4896.127 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["items"])
    temp_df.columns = [
        "股票代码",
        "股票名称",
        "变动人",
        "-",
        "变动日期",
        "变动股数",
        "成交均价",
        "变动后持股数",
        "与董监高关系",
        "董监高职务",
    ]
    temp_df = temp_df[
        [
            "股票代码",
            "股票名称",
            "变动日期",
            "变动人",
            "变动股数",
            "成交均价",
            "变动后持股数",
            "与董监高关系",
            "董监高职务",
        ]
    ]
    temp_df["变动日期"] = (
        pd.to_datetime(temp_df["变动日期"], unit="ms", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.date
    )
    temp_df["变动股数"] = pd.to_numeric(temp_df["变动股数"], errors="coerce")
    temp_df["成交均价"] = pd.to_numeric(temp_df["成交均价"], errors="coerce")
    temp_df["变动后持股数"] = pd.to_numeric(temp_df["变动后持股数"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    stock_inner_trade_xq_df = stock_inner_trade_xq()
    print(stock_inner_trade_xq_df)
