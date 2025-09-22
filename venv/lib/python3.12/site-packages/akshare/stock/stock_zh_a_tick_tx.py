#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/10/27 22:08
Desc: 腾讯-股票-实时行情-成交明细
成交明细-每个交易日 16:00 提供当日数据
港股报价延时 15 分钟
"""

import warnings

import pandas as pd
import requests


def stock_zh_a_tick_tx_js(symbol: str = "sz000001") -> pd.DataFrame:
    """
    腾讯财经-历史分笔数据
    https://gu.qq.com/sz300494/gp/detail
    :param symbol: 股票代码
    :type symbol: str
    :return: 历史分笔数据
    :rtype: pandas.DataFrame
    """
    big_df = pd.DataFrame()
    page = 0
    warnings.warn("正在下载数据，请稍等")
    while True:
        try:
            url = "http://stock.gtimg.cn/data/index.php"
            params = {
                "appn": "detail",
                "action": "data",
                "c": symbol,
                "p": page,
            }
            r = requests.get(url, params=params)
            text_data = r.text
            temp_df = (
                pd.DataFrame(eval(text_data[text_data.find("[") :])[1].split("|"))
                .iloc[:, 0]
                .str.split("/", expand=True)
            )
            page += 1
            big_df = pd.concat([big_df, temp_df], ignore_index=True)
        except:  # noqa: E722
            break
    if not big_df.empty:
        big_df = big_df.iloc[:, 1:].copy()
        big_df.columns = [
            "成交时间",
            "成交价格",
            "价格变动",
            "成交量",
            "成交金额",
            "性质",
        ]
        big_df.reset_index(drop=True, inplace=True)
        property_map = {
            "S": "卖盘",
            "B": "买盘",
            "M": "中性盘",
        }
        big_df["性质"] = big_df["性质"].map(property_map)
        big_df = big_df.astype(
            {
                "成交时间": str,
                "成交价格": float,
                "价格变动": float,
                "成交量": int,
                "成交金额": int,
                "性质": str,
            }
        )
    return big_df


if __name__ == "__main__":
    stock_zh_a_tick_tx_js_df = stock_zh_a_tick_tx_js(symbol="sz000001")
    print(stock_zh_a_tick_tx_js_df)
