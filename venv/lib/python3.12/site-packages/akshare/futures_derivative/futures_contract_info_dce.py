#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/2/28 11:00
Desc: 大连商品交易所-业务/服务-业务参数-交易参数-合约信息查询
http://www.dce.com.cn/dalianshangpin/ywfw/ywcs/jycs/hyxxcx/index.html
"""

from io import StringIO

import pandas as pd
import requests


def futures_contract_info_dce() -> pd.DataFrame:
    """
    大连商品交易所-业务/服务-业务参数-交易参数-合约信息查询
    http://www.dce.com.cn/dalianshangpin/ywfw/ywcs/jycs/hyxxcx/index.html
    :return: 交易参数汇总查询
    :rtype: pandas.DataFrame
    """
    url = "http://www.dce.com.cn/publicweb/businessguidelines/queryContractInfo.html"
    params = {
        "contractInformation.variety": "all",
        "contractInformation.trade_type": "0",
    }
    r = requests.post(url, params=params)
    temp_df = pd.read_html(StringIO(r.text))[0]
    temp_df["交易单位"] = pd.to_numeric(temp_df["交易单位"], errors="coerce")
    temp_df["最小变动价位"] = pd.to_numeric(temp_df["最小变动价位"], errors="coerce")
    temp_df["最小变动价位"] = pd.to_numeric(temp_df["最小变动价位"], errors="coerce")
    temp_df["开始交易日"] = pd.to_datetime(
        temp_df["开始交易日"], format="%Y%m%d", errors="coerce"
    ).dt.date
    temp_df["最后交易日"] = pd.to_datetime(
        temp_df["最后交易日"], format="%Y%m%d", errors="coerce"
    ).dt.date
    temp_df["最后交割日"] = pd.to_datetime(
        temp_df["最后交割日"], format="%Y%m%d", errors="coerce"
    ).dt.date
    return temp_df


if __name__ == "__main__":
    futures_contract_info_dce_df = futures_contract_info_dce()
    print(futures_contract_info_dce_df)
