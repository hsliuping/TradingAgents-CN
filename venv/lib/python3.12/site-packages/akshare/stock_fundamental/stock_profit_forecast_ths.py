#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/1 15:00
Desc: 同花顺-盈利预测
https://basic.10jqka.com.cn/new/600519/worth.html
"""

from io import StringIO

import pandas as pd
import requests

from akshare.utils.cons import headers


def stock_profit_forecast_ths(
    symbol: str = "600519", indicator: str = "预测年报每股收益"
) -> pd.DataFrame:
    """
    同花顺-盈利预测
    https://basic.10jqka.com.cn/new/600519/worth.html
    :param symbol: 股票代码
    :type symbol: str
    :param indicator: choice of {"预测年报每股收益", "预测年报净利润", "业绩预测详表-机构", "业绩预测详表-详细指标预测"}
    :type indicator: str
    :return: 盈利预测
    :rtype: pandas.DataFrame
    """
    url = f"https://basic.10jqka.com.cn/new/{symbol}/worth.html"
    r = requests.get(url, headers=headers)
    r.encoding = "gbk"
    if "本年度暂无机构做出业绩预测" in r.text:
        # 处理 `本年度暂无机构做出业绩预测` 的情况
        if indicator == "预测年报每股收益":
            return pd.DataFrame()
        elif indicator == "预测年报净利润":
            return pd.DataFrame()
        elif indicator == "业绩预测详表-机构":
            temp_df = pd.read_html(StringIO(r.text))[0]
            columns_list = []
            for item in temp_df.columns:
                columns_list.append(item[1])
            columns_list[2] = "预测年报每股收益" + columns_list[2]
            columns_list[3] = "预测年报每股收益" + columns_list[3]
            columns_list[4] = "预测年报每股收益" + columns_list[4]
            columns_list[5] = "预测年报净利润" + columns_list[5]
            columns_list[6] = "预测年报净利润" + columns_list[6]
            columns_list[7] = "预测年报净利润" + columns_list[7]
            temp_df.columns = columns_list
            temp_df["报告日期"] = pd.to_datetime(
                temp_df["报告日期"], errors="coerce"
            ).dt.date
            return temp_df
        elif indicator == "业绩预测详表-详细指标预测":
            temp_df = pd.read_html(StringIO(r.text))[1]
            temp_df.columns = [
                item.replace("（", "-").replace("）", "") for item in temp_df.columns
            ]
            return temp_df
        else:
            return pd.DataFrame()
    else:
        if indicator == "预测年报每股收益":
            temp_df = pd.read_html(StringIO(r.text))[0]
            temp_df["年度"] = temp_df["年度"].astype(str)
            return temp_df
        elif indicator == "预测年报净利润":
            temp_df = pd.read_html(StringIO(r.text))[1]
            temp_df["年度"] = temp_df["年度"].astype(str)
            return temp_df
        elif indicator == "业绩预测详表-机构":
            temp_df = pd.read_html(StringIO(r.text))[2]
            columns_list = []
            for item in temp_df.columns:
                columns_list.append(item[1])
            columns_list[2] = "预测年报每股收益" + columns_list[2]
            columns_list[3] = "预测年报每股收益" + columns_list[3]
            columns_list[4] = "预测年报每股收益" + columns_list[4]
            columns_list[5] = "预测年报净利润" + columns_list[5]
            columns_list[6] = "预测年报净利润" + columns_list[6]
            columns_list[7] = "预测年报净利润" + columns_list[7]
            temp_df.columns = columns_list
            temp_df["报告日期"] = pd.to_datetime(temp_df["报告日期"]).dt.date
            return temp_df
        elif indicator == "业绩预测详表-详细指标预测":
            temp_df = pd.read_html(StringIO(r.text))[3]
            temp_df.columns = [
                item.replace("（", "-").replace("）", "") for item in temp_df.columns
            ]
            return temp_df
        else:
            return pd.DataFrame()


if __name__ == "__main__":
    stock_profit_forecast_ths_df = stock_profit_forecast_ths(
        symbol="600519", indicator="预测年报每股收益"
    )
    print(stock_profit_forecast_ths_df)

    stock_profit_forecast_ths_df = stock_profit_forecast_ths(
        symbol="600519", indicator="预测年报净利润"
    )
    print(stock_profit_forecast_ths_df)

    stock_profit_forecast_ths_df = stock_profit_forecast_ths(
        symbol="600519", indicator="业绩预测详表-机构"
    )
    print(stock_profit_forecast_ths_df)

    stock_profit_forecast_ths_df = stock_profit_forecast_ths(
        symbol="600519", indicator="业绩预测详表-详细指标预测"
    )
    print(stock_profit_forecast_ths_df)
