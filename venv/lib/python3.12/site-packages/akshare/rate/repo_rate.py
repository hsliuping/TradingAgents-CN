#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/1/20 23:04
Desc: 中国外汇交易中心暨全国银行间同业拆借中心-回购定盘利率-历史数据
"""

import pandas as pd
import requests


def repo_rate_query(symbol: str = "回购定盘利率") -> pd.DataFrame:
    """
    中国外汇交易中心暨全国银行间同业拆借中心-回购定盘利率-历史数据
    https://www.chinamoney.com.cn/chinese/bkfrr/
    :param symbol: choice of {"回购定盘利率", "银银间回购定盘利率"}
    :type symbol: str
    :return: 回购定盘利率-历史数据
    :rtype: pandas.DataFrame
    """
    if symbol == "回购定盘利率":
        url = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/currency/frr-chrt.csv"
        temp_df = pd.read_csv(url, header=None)
        temp_df.dropna(axis=1, inplace=True)
        temp_df.columns = ["date", "FR001", "FR007", "FR014"]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["FR001"] = pd.to_numeric(temp_df["FR001"], errors="coerce")
        temp_df["FR007"] = pd.to_numeric(temp_df["FR007"], errors="coerce")
        temp_df["FR014"] = pd.to_numeric(temp_df["FR014"], errors="coerce")
        temp_df.sort_values(by=["date"], ignore_index=True, inplace=True)
        return temp_df
    else:
        url = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/currency/fdr-chrt.csv"
        temp_df = pd.read_csv(url, header=None)
        temp_df.dropna(axis=1, inplace=True)
        temp_df.columns = ["date", "FDR001", "FDR007", "FDR014"]
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        temp_df["FDR001"] = pd.to_numeric(temp_df["FDR001"], errors="coerce")
        temp_df["FDR007"] = pd.to_numeric(temp_df["FDR007"], errors="coerce")
        temp_df["FDR014"] = pd.to_numeric(temp_df["FDR014"], errors="coerce")
        temp_df.sort_values(by=["date"], ignore_index=True, inplace=True)
        return temp_df


def repo_rate_hist(
    start_date: str = "20200930", end_date: str = "20201029"
) -> pd.DataFrame:
    """
    中国外汇交易中心暨全国银行间同业拆借中心-回购定盘利率-历史数据
    https://www.chinamoney.com.cn/chinese/bkfrr/
    :param start_date: 开始时间, 开始时间与结束时间需要在一个月内
    :type start_date: str
    :param end_date: 结束时间, 开始时间与结束时间需要在一个月内
    :type end_date: str
    :return: 回购定盘利率-历史数据
    :rtype: pandas.DataFrame
    """
    start_date = "-".join([start_date[:4], start_date[4:6], start_date[6:]])
    end_date = "-".join([end_date[:4], end_date[4:6], end_date[6:]])
    url = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-currency/FrrHis"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    }
    params = {
        "lang": "CN",
        "startDate": start_date,
        "endDate": end_date,
    }
    r = requests.post(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df = pd.DataFrame([item for item in temp_df["frValueMap"].to_list()])
    temp_df = temp_df[
        [
            "date",
            "FR001",
            "FR007",
            "FR014",
            "FDR001",
            "FDR007",
            "FDR014",
        ]
    ]
    temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
    temp_df["FR001"] = pd.to_numeric(temp_df["FR001"], errors="coerce")
    temp_df["FR007"] = pd.to_numeric(temp_df["FR007"], errors="coerce")
    temp_df["FR014"] = pd.to_numeric(temp_df["FR014"], errors="coerce")
    temp_df["FDR001"] = pd.to_numeric(temp_df["FDR001"], errors="coerce")
    temp_df["FDR007"] = pd.to_numeric(temp_df["FDR007"], errors="coerce")
    temp_df["FDR014"] = pd.to_numeric(temp_df["FDR014"], errors="coerce")
    temp_df.sort_values(["date"], ignore_index=True, inplace=True)
    return temp_df


if __name__ == "__main__":
    repo_rate_query_df = repo_rate_query(symbol="回购定盘利率")
    print(repo_rate_query_df)

    repo_rate_hist_df = repo_rate_hist(start_date="20231001", end_date="20240101")
    print(repo_rate_hist_df)
