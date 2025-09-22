#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/2/28 16:00
Desc: 广州期货交易所-业务/服务-合约信息
http://www.gfex.com.cn/gfex/hyxx/ywcs.shtml
"""

import pandas as pd
import requests


def futures_contract_info_gfex() -> pd.DataFrame:
    """
    广州期货交易所-业务/服务-合约信息
    http://www.gfex.com.cn/gfex/hyxx/ywcs.shtml
    :return: 交易参数汇总查询
    :rtype: pandas.DataFrame
    """
    url = "http://www.gfex.com.cn/u/interfacesWebTtQueryContractInfo/loadList"
    params = {
        "variety": "",
        "trade_type": "0",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    r = requests.post(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"])
    temp_df.rename(
        columns={
            "tradeType": "-",
            "variety": "品种",
            "varietyOrder": "-",
            "contractId": "合约代码",
            "unit": "交易单位",
            "tick": "最小变动单位",
            "startTradeDate": "开始交易日",
            "endTradeDate": "最后交易日",
            "endDeliveryDate0": "最后交割日",
        },
        inplace=True,
    )
    temp_df["交易单位"] = pd.to_numeric(temp_df["交易单位"], errors="coerce")
    temp_df["最小变动单位"] = pd.to_numeric(temp_df["最小变动单位"], errors="coerce")
    temp_df["开始交易日"] = pd.to_datetime(
        temp_df["开始交易日"], format="%Y%m%d", errors="coerce"
    ).dt.date
    temp_df["最后交易日"] = pd.to_datetime(
        temp_df["最后交易日"], format="%Y%m%d", errors="coerce"
    ).dt.date
    temp_df["最后交割日"] = pd.to_datetime(
        temp_df["最后交割日"], format="%Y%m%d", errors="coerce"
    ).dt.date
    temp_df = temp_df[
        [
            "品种",
            "合约代码",
            "交易单位",
            "最小变动单位",
            "开始交易日",
            "最后交易日",
            "最后交割日",
        ]
    ]
    return temp_df


if __name__ == "__main__":
    futures_contract_info_gfex_df = futures_contract_info_gfex()
    print(futures_contract_info_gfex_df)
