#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/10/1 17:00
Desc: 中国外汇交易中心暨全国银行间同业拆借中心
中国外汇交易中心暨全国银行间同业拆借中心-市场数据-债券市场行情-现券市场做市报价
中国外汇交易中心暨全国银行间同业拆借中心-市场数据-债券市场行情-现券市场成交行情
https://www.chinamoney.com.cn/chinese/mkdatabond/
"""

from io import StringIO

import pandas as pd
import requests

from akshare.bond.bond_china_money import bond_china_close_return_map
from akshare.utils.cons import headers


def bond_spot_quote() -> pd.DataFrame:
    """
    中国外汇交易中心暨全国银行间同业拆借中心-市场数据-债券市场行情-现券市场做市报价
    https://www.chinamoney.com.cn/chinese/mkdatabond/
    :return: 现券市场做市报价
    :rtype: pandas.DataFrame
    """
    bond_china_close_return_map()
    url = "https://www.chinamoney.com.cn/ags/ms/cm-u-md-bond/CbMktMakQuot"
    payload = {
        "flag": "1",
        "lang": "cn",
    }
    r = requests.post(url=url, data=payload, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "_",
        "_",
        "报价机构",
        "_",
        "_",
        "_",
        "债券简称",
        "_",
        "_",
        "_",
        "_",
        "买入/卖出收益率",
        "_",
        "买入/卖出净价",
        "_",
        "_",
        "_",
    ]
    temp_df = temp_df[
        [
            "报价机构",
            "债券简称",
            "买入/卖出净价",
            "买入/卖出收益率",
        ]
    ]
    temp_df["买入净价"] = (
        temp_df["买入/卖出净价"].str.split("/", expand=True).iloc[:, 0]
    )
    temp_df["卖出净价"] = (
        temp_df["买入/卖出净价"].str.split("/", expand=True).iloc[:, 1]
    )
    temp_df["买入收益率"] = (
        temp_df["买入/卖出收益率"].str.split("/", expand=True).iloc[:, 0]
    )
    temp_df["卖出收益率"] = (
        temp_df["买入/卖出收益率"].str.split("/", expand=True).iloc[:, 1]
    )
    del temp_df["买入/卖出净价"]
    del temp_df["买入/卖出收益率"]
    temp_df["买入净价"] = pd.to_numeric(temp_df["买入净价"], errors="coerce")
    temp_df["卖出净价"] = pd.to_numeric(temp_df["卖出净价"], errors="coerce")
    temp_df["买入收益率"] = pd.to_numeric(temp_df["买入收益率"], errors="coerce")
    temp_df["卖出收益率"] = pd.to_numeric(temp_df["卖出收益率"], errors="coerce")
    return temp_df


def bond_spot_deal() -> pd.DataFrame:
    """
    中国外汇交易中心暨全国银行间同业拆借中心-市场数据-债券市场行情-现券市场成交行情
    https://www.chinamoney.com.cn/chinese/mkdatabond/
    :return: 现券市场成交行情
    :rtype: pandas.DataFrame
    """
    url = "https://www.chinamoney.com.cn/ags/ms/cm-u-md-bond/CbtPri"
    payload = {
        "flag": "1",
        "lang": "cn",
        "bondName": "",
    }
    r = requests.post(url=url, data=payload, headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["records"])
    temp_df.columns = [
        "_",
        "_",
        "债券简称",
        "_",
        "_",
        "_",
        "_",
        "涨跌",
        "_",
        "_",
        "_",
        "加权收益率",
        "成交净价",
        "_",
        "_",
        "最新收益率",
        "-",
        "交易量",
        "_",
        "_",
        "_",
        "_",
    ]
    temp_df = temp_df[
        [
            "债券简称",
            "成交净价",
            "最新收益率",
            "涨跌",
            "加权收益率",
            "交易量",
        ]
    ]
    temp_df["成交净价"] = pd.to_numeric(temp_df["成交净价"], errors="coerce")
    temp_df["最新收益率"] = pd.to_numeric(temp_df["最新收益率"], errors="coerce")
    temp_df["涨跌"] = pd.to_numeric(temp_df["涨跌"], errors="coerce")
    temp_df["加权收益率"] = pd.to_numeric(temp_df["加权收益率"], errors="coerce")
    temp_df["交易量"] = pd.to_numeric(temp_df["交易量"], errors="coerce")
    return temp_df


def bond_china_yield(
    start_date: str = "20200204", end_date: str = "20210124"
) -> pd.DataFrame:
    """
    中国债券信息网-国债及其他债券收益率曲线
    https://www.chinabond.com.cn/
    https://yield.chinabond.com.cn/cbweb-pbc-web/pbc/historyQuery?startDate=2019-02-07&endDate=2020-02-04&gjqx=0&qxId=ycqx&locale=cn_ZH
    注意: end_date - start_date 应该小于一年
    :param start_date: 需要查询的日期, 返回在该日期之后一年内的数据
    :type start_date: str
    :param end_date: 需要查询的日期, 返回在该日期之前一年内的数据
    :type end_date: str
    :return: 返回在指定日期之间之前一年内的数据
    :rtype: pandas.DataFrame
    """
    url = "https://yield.chinabond.com.cn/cbweb-pbc-web/pbc/historyQuery"
    params = {
        "startDate": "-".join([start_date[:4], start_date[4:6], start_date[6:]]),
        "endDate": "-".join([end_date[:4], end_date[4:6], end_date[6:]]),
        "gjqx": "0",
        "qxId": "ycqx",
        "locale": "cn_ZH",
    }
    res = requests.get(url, params=params, headers=headers)
    data_text = res.text.replace("&nbsp", "")
    data_df = pd.read_html(StringIO(data_text), header=0)[1]
    data_df["日期"] = pd.to_datetime(data_df["日期"], errors="coerce").dt.date
    data_df["3月"] = pd.to_numeric(data_df["3月"], errors="coerce")
    data_df["6月"] = pd.to_numeric(data_df["6月"], errors="coerce")
    data_df["1年"] = pd.to_numeric(data_df["1年"], errors="coerce")
    data_df["3年"] = pd.to_numeric(data_df["3年"], errors="coerce")
    data_df["5年"] = pd.to_numeric(data_df["5年"], errors="coerce")
    data_df["7年"] = pd.to_numeric(data_df["7年"], errors="coerce")
    data_df["10年"] = pd.to_numeric(data_df["10年"], errors="coerce")
    data_df["30年"] = pd.to_numeric(data_df["30年"], errors="coerce")
    data_df.sort_values(by="日期", inplace=True)
    data_df.reset_index(inplace=True, drop=True)
    return data_df


if __name__ == "__main__":
    bond_spot_quote_df = bond_spot_quote()
    print(bond_spot_quote_df)

    bond_spot_deal_df = bond_spot_deal()
    print(bond_spot_deal_df)

    bond_china_yield_df = bond_china_yield(start_date="20210201", end_date="20220201")
    print(bond_china_yield_df)
