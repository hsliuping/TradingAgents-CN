#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/11/30 19:00
Desc: 上海国际能源交易中心-业务指南-交易参数汇总(期货)
https://www.ine.cn/bourseService/summary/?name=currinstrumentprop
"""

import pandas as pd
import requests


def futures_contract_info_ine(date: str = "20241129") -> pd.DataFrame:
    """
    上海国际能源交易中心-业务指南-交易参数汇总(期货)
    https://www.ine.cn/bourseService/summary/?name=currinstrumentprop
    :param date: 查询日期; 交易日
    :type date: str
    :return: 交易参数汇总查询
    :rtype: pandas.DataFrame
    """
    url = f"https://www.ine.cn/data/busiparamdata/future/ContractBaseInfo{date}.dat"
    params = {"rnd": "0.8312696798757147"}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["ContractBaseInfo"])
    temp_df.rename(
        columns={
            "BASISPRICE": "挂牌基准价",
            "ENDDELIVDATE": "最后交割日",
            "EXPIREDATE": "到期日",
            "INSTRUMENTID": "合约代码",
            "OPENDATE": "上市日",
            "STARTDELIVDATE": "开始交割日",
            "TRADINGDAY": "交易日",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "合约代码",
            "上市日",
            "到期日",
            "开始交割日",
            "最后交割日",
            "挂牌基准价",
            "交易日",
        ]
    ]
    temp_df["上市日"] = pd.to_datetime(temp_df["上市日"], errors="coerce").dt.date
    temp_df["到期日"] = pd.to_datetime(temp_df["到期日"], errors="coerce").dt.date
    temp_df["开始交割日"] = pd.to_datetime(
        temp_df["开始交割日"], errors="coerce"
    ).dt.date
    temp_df["最后交割日"] = pd.to_datetime(
        temp_df["最后交割日"], errors="coerce"
    ).dt.date
    temp_df["交易日"] = pd.to_datetime(temp_df["交易日"], errors="coerce").dt.date
    temp_df["挂牌基准价"] = pd.to_numeric(temp_df["挂牌基准价"], errors="coerce")
    return temp_df


if __name__ == "__main__":
    futures_contract_info_ine_df = futures_contract_info_ine(date="20241129")
    print(futures_contract_info_ine_df)
