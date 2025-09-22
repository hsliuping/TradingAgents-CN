#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/5 18:00
Desc: 新浪财经-期货-成交持仓
https://vip.stock.finance.sina.com.cn/q/view/vFutures_Positions_cjcc.php
"""

from io import StringIO

import pandas as pd
import requests


def futures_hold_pos_sina(
    symbol: str = "成交量", contract: str = "OI2501", date: str = "20240223"
) -> pd.DataFrame:
    """
    新浪财经-期货-成交持仓
    https://vip.stock.finance.sina.com.cn/q/view/vFutures_Positions_cjcc.php
    :param symbol: choice of {"成交量", "多单持仓", "空单持仓"}
    :type symbol: str
    :param contract: 期货合约
    :type contract: str
    :param date: 查询日期
    :type date: str
    :return: 成交持仓
    :rtype: pandas.DataFrame
    """
    date = "-".join([date[:4], date[4:6], date[6:]])
    url = "https://vip.stock.finance.sina.com.cn/q/view/vFutures_Positions_cjcc.php"
    params = {"t_breed": contract, "t_date": date}
    r = requests.get(url, params=params)
    if symbol == "成交量":
        temp_df = pd.read_html(StringIO(r.text))[2].iloc[:-1, :]
        temp_df["名次"] = pd.to_numeric(temp_df["名次"], errors="coerce")
        temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
        temp_df["比上交易增减"] = pd.to_numeric(
            temp_df["比上交易增减"], errors="coerce"
        )
        return temp_df
    elif symbol == "多单持仓":
        temp_df = pd.read_html(StringIO(r.text))[3].iloc[:-1, :]
        temp_df["名次"] = pd.to_numeric(temp_df["名次"], errors="coerce")
        temp_df["多单持仓"] = pd.to_numeric(temp_df["多单持仓"], errors="coerce")
        temp_df["比上交易增减"] = pd.to_numeric(
            temp_df["比上交易增减"], errors="coerce"
        )
        return temp_df
    elif symbol == "空单持仓":
        temp_df = pd.read_html(StringIO(r.text))[4].iloc[:-1, :]
        temp_df["名次"] = pd.to_numeric(temp_df["名次"], errors="coerce")
        temp_df["空单持仓"] = pd.to_numeric(temp_df["空单持仓"], errors="coerce")
        temp_df["比上交易增减"] = pd.to_numeric(
            temp_df["比上交易增减"], errors="coerce"
        )
        return temp_df
    else:
        raise ValueError("请输入正确的 symbol 参数")


if __name__ == "__main__":
    futures_hold_pos_sina_df = futures_hold_pos_sina(
        symbol="成交量", contract="IC2403", date="20240203"
    )
    print(futures_hold_pos_sina_df)

    futures_hold_pos_sina_df = futures_hold_pos_sina(
        symbol="多单持仓", contract="OI2501", date="20241016"
    )
    print(futures_hold_pos_sina_df)

    futures_hold_pos_sina_df = futures_hold_pos_sina(
        symbol="空单持仓", contract="OI2501", date="20241016"
    )
    print(futures_hold_pos_sina_df)
