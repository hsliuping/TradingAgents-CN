#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/5/13 17:45
Desc: 上海期货交易所-交易所服务-业务数据-交易参数汇总查询
https://tsite.shfe.com.cn/bourseService/businessdata/summaryinquiry/
"""

import pandas as pd
import requests


def futures_contract_info_shfe(date: str = "20240513") -> pd.DataFrame:
    """
    上海期货交易所-交易所服务-业务数据-交易参数汇总查询
    https://tsite.shfe.com.cn/bourseService/businessdata/summaryinquiry/
    :param date: 查询日期; 交易日
    :type date: str
    :return: 交易参数汇总查询
    :rtype: pandas.DataFrame
    """
    url = f"https://www.shfe.com.cn/data/busiparamdata/future/ContractBaseInfo{date}.dat"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    }
    r = requests.get(url, headers=headers)
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
    temp_df["更新时间"] = data_json['update_date']
    return temp_df


if __name__ == "__main__":
    futures_contract_info_shfe_df = futures_contract_info_shfe(date="20250611")
    print(futures_contract_info_shfe_df)
