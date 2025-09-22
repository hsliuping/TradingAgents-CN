# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2025/2/19 22:00
Desc: 参考汇率和结算汇率
深港通-港股通业务信息
深港通-港股通业务信息: https://www.szse.cn/szhk/hkbussiness/exchangerate/index.html
沪港通-港股通信息披露: https://www.sse.com.cn/services/hkexsc/disclo/ratios/
"""

import warnings
from datetime import datetime

import pandas as pd
import requests


def stock_sgt_settlement_exchange_rate_szse() -> pd.DataFrame:
    """
    深港通-港股通业务信息-结算汇率
    https://www.szse.cn/szhk/hkbussiness/exchangerate/index.html
    :return: 结算汇率
    :rtype: pandas.DataFrame
    """
    url = "https://www.szse.cn/api/report/ShowReport"
    params = {
        "SHOWTYPE": "xlsx",
        "CATALOGID": "SGT_LSHL",
        "TABKEY": "tab2",
        "random": "0.9184251620553985",
    }
    r = requests.get(url, params=params)
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        temp_df = pd.read_excel(r.content, engine="openpyxl")
    temp_df.sort_values(by="适用日期", inplace=True, ignore_index=True)
    temp_df["适用日期"] = pd.to_datetime(temp_df["适用日期"], errors="coerce").dt.date
    temp_df["买入结算汇兑比率"] = pd.to_numeric(
        temp_df["买入结算汇兑比率"], errors="coerce"
    )
    temp_df["卖出结算汇兑比率"] = pd.to_numeric(
        temp_df["卖出结算汇兑比率"], errors="coerce"
    )
    return temp_df


def stock_sgt_reference_exchange_rate_szse() -> pd.DataFrame:
    """
    深港通-港股通业务信息-参考汇率
    https://www.szse.cn/szhk/hkbussiness/exchangerate/index.html
    :return: 参考汇率
    :rtype: pandas.DataFrame
    """
    url = "https://www.szse.cn/api/report/ShowReport"
    params = {
        "SHOWTYPE": "xlsx",
        "CATALOGID": "SGT_LSHL",
        "TABKEY": "tab1",
        "random": "0.9184251620553985",
    }
    r = requests.get(url, params=params)
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        temp_df = pd.read_excel(r.content, engine="openpyxl")
    temp_df.sort_values(by="适用日期", inplace=True, ignore_index=True)
    temp_df["适用日期"] = pd.to_datetime(temp_df["适用日期"], errors="coerce").dt.date
    temp_df["参考汇率买入价"] = pd.to_numeric(
        temp_df["参考汇率买入价"], errors="coerce"
    )
    temp_df["参考汇率卖出价"] = pd.to_numeric(
        temp_df["参考汇率卖出价"], errors="coerce"
    )
    return temp_df


def stock_sgt_reference_exchange_rate_sse() -> pd.DataFrame:
    """
    沪港通-港股通信息披露-参考汇率
    https://www.sse.com.cn/services/hkexsc/disclo/ratios/
    :return: 参考汇率
    :rtype: pandas.DataFrame
    """
    current_date = datetime.now().date().isoformat().replace("-", "")
    url = "https://query.sse.com.cn/commonSoaQuery.do"
    params = {
        "isPagination": "true",
        "updateDate": "20120601",
        "updateDateEnd": current_date,
        "sqlId": "FW_HGT_GGTHL",
        "pageHelp.cacheSize": "1",
        "pageHelp.pageSize": "10000",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.endPage": "1",
    }
    headers = {
        "Host": "query.sse.com.cn",
        "Referer": "https://www.sse.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/105.0.0.0 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"])
    temp_df.rename(
        columns={
            "currencyType": "货币种类",
            "buyPrice": "参考汇率买入价",
            "updateDate": "-",
            "validDate": "适用日期",
            "sellPrice": "参考汇率卖出价",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "适用日期",
            "参考汇率买入价",
            "参考汇率卖出价",
            "货币种类",
        ]
    ]
    temp_df.sort_values("适用日期", inplace=True, ignore_index=True)
    temp_df["适用日期"] = pd.to_datetime(temp_df["适用日期"], errors="coerce").dt.date
    temp_df["参考汇率买入价"] = pd.to_numeric(
        temp_df["参考汇率买入价"], errors="coerce"
    )
    temp_df["参考汇率卖出价"] = pd.to_numeric(
        temp_df["参考汇率卖出价"], errors="coerce"
    )
    return temp_df


def stock_sgt_settlement_exchange_rate_sse() -> pd.DataFrame:
    """
    沪港通-港股通信息披露-结算汇兑
    https://www.sse.com.cn/services/hkexsc/disclo/ratios/
    :return: 结算汇兑比率
    :rtype: pandas.DataFrame
    """
    current_date = datetime.now().date().isoformat().replace("-", "")
    url = "https://query.sse.com.cn/commonSoaQuery.do"
    params = {
        "isPagination": "true",
        "updateDate": "20120601",
        "updateDateEnd": current_date,
        "sqlId": "FW_HGT_JSHDBL",
        "pageHelp.cacheSize": "1",
        "pageHelp.pageSize": "10000",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.endPage": "1",
    }
    headers = {
        "Host": "query.sse.com.cn",
        "Referer": "https://www.sse.com.cn/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/105.0.0.0 Safari/537.36",
    }
    r = requests.get(url, params=params, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["result"])
    temp_df.rename(
        columns={
            "currencyType": "货币种类",
            "buyPrice": "买入结算汇兑比率",
            "updateDate": "-",
            "validDate": "适用日期",
            "sellPrice": "卖出结算汇兑比率",
        },
        inplace=True,
    )
    temp_df = temp_df[
        [
            "适用日期",
            "买入结算汇兑比率",
            "卖出结算汇兑比率",
            "货币种类",
        ]
    ]
    temp_df.sort_values("适用日期", inplace=True, ignore_index=True)
    temp_df["适用日期"] = pd.to_datetime(temp_df["适用日期"], errors="coerce").dt.date
    temp_df["买入结算汇兑比率"] = pd.to_numeric(
        temp_df["买入结算汇兑比率"], errors="coerce"
    )
    temp_df["卖出结算汇兑比率"] = pd.to_numeric(
        temp_df["卖出结算汇兑比率"], errors="coerce"
    )
    return temp_df


if __name__ == "__main__":
    stock_sgt_settlement_exchange_rate_szse_df = (
        stock_sgt_settlement_exchange_rate_szse()
    )
    print(stock_sgt_settlement_exchange_rate_szse_df)

    stock_sgt_reference_exchange_rate_szse_df = stock_sgt_reference_exchange_rate_szse()
    print(stock_sgt_reference_exchange_rate_szse_df)

    stock_sgt_reference_exchange_rate_sse_df = stock_sgt_reference_exchange_rate_sse()
    print(stock_sgt_reference_exchange_rate_sse_df)

    stock_sgt_settlement_exchange_rate_sse_df = stock_sgt_settlement_exchange_rate_sse()
    print(stock_sgt_settlement_exchange_rate_sse_df)
