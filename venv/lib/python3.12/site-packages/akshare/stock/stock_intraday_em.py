#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/10 18:00
Desc: 东财财富-日内分时数据
https://quote.eastmoney.com/f1.html?newcode=0.000001
"""

import json

import pandas as pd
import requests


def __event_stream(url, params):
    # 使用 stream=True 参数来启用流式请求
    response = requests.get(url, params=params, stream=True)
    event_data = ""

    for line in response.iter_lines():
        # 过滤掉保持连接的空行
        if line:
            event_data += line.decode() + "\n"
        elif event_data:
            yield event_data
            event_data = ""


def stock_intraday_em(symbol: str = "000001") -> pd.DataFrame:
    """
    东方财富-分时数据
    https://quote.eastmoney.com/f1.html?newcode=0.000001
    :param symbol: 股票代码
    :type symbol: str
    :return: 分时数据
    :rtype: pandas.DataFrame
    """
    market_code = 1 if symbol.startswith("6") else 0
    url = "https://70.push2.eastmoney.com/api/qt/stock/details/sse"
    params = {
        "fields1": "f1,f2,f3,f4",
        "fields2": "f51,f52,f53,f54,f55",
        "mpi": "2000",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "pos": "-0",
        "secid": f"{market_code}.{symbol}",
        "wbp2u": "|0|0|0|web",
    }

    big_df = pd.DataFrame()  # 创建一个空的 DataFrame

    for event in __event_stream(url, params):
        # 从每个事件的数据行中删除 "data: "，然后解析 JSON
        event_json = json.loads(event.replace("data: ", ""))
        # 将 JSON 数据转换为 DataFrame，然后添加到主 DataFrame 中
        temp_df = pd.DataFrame(
            [item.split(",") for item in event_json["data"]["details"]]
        )
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
        break

    big_df.columns = ["时间", "成交价", "手数", "-", "买卖盘性质"]
    big_df["买卖盘性质"] = big_df["买卖盘性质"].map(
        {"2": "买盘", "1": "卖盘", "4": "中性盘"}
    )
    big_df = big_df[["时间", "成交价", "手数", "买卖盘性质"]]
    big_df["成交价"] = pd.to_numeric(big_df["成交价"], errors="coerce")
    big_df["手数"] = pd.to_numeric(big_df["手数"], errors="coerce")
    return big_df


if __name__ == "__main__":
    stock_intraday_em_df = stock_intraday_em(symbol="000001")
    print(stock_intraday_em_df)
