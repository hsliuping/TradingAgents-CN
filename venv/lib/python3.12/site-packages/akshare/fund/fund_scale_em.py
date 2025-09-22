# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2023/10/27 20:30
Desc: 天天基金网-基金数据-规模份额
https://fund.eastmoney.com/data/cyrjglist.html
"""

import pandas as pd
import requests

from akshare.utils import demjson


def fund_scale_change_em() -> pd.DataFrame:
    """
    天天基金网-基金数据-规模份额-规模变动
    https://fund.eastmoney.com/data/gmbdlist.html
    :return: 规模变动
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/data/FundDataPortfolio_Interface.aspx"
    params = {
        "dt": "9",
        "pi": "1",
        "pn": "50",
        "mc": "hypzDetail",
        "st": "desc",
        "sc": "reportdate",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -1])
    total_page = data_json["pages"]
    big_df = pd.DataFrame()
    for page in range(1, int(total_page) + 1):
        params.update({"pi": page})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -1])
        temp_df = pd.DataFrame(data_json["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df["index"] + 1
    big_df.columns = [
        "序号",
        "截止日期",
        "基金家数",
        "期间申购",
        "期间赎回",
        "期末总份额",
        "期末净资产",
    ]
    big_df["截止日期"] = pd.to_datetime(big_df["截止日期"], errors="coerce").dt.date
    big_df["基金家数"] = pd.to_numeric(big_df["基金家数"], errors="coerce")
    big_df["期间申购"] = pd.to_numeric(
        big_df["期间申购"].str.replace(",", ""), errors="coerce"
    )
    big_df["期间赎回"] = pd.to_numeric(
        big_df["期间赎回"].str.replace(",", ""), errors="coerce"
    )
    big_df["期末总份额"] = pd.to_numeric(
        big_df["期末总份额"].str.replace(",", ""), errors="coerce"
    )
    big_df["期末净资产"] = pd.to_numeric(
        big_df["期末净资产"].str.replace(",", ""), errors="coerce"
    )
    return big_df


def fund_hold_structure_em() -> pd.DataFrame:
    """
    天天基金网-基金数据-规模份额-持有人结构
    https://fund.eastmoney.com/data/cyrjglist.html
    :return: 持有人结构
    :rtype: pandas.DataFrame
    """
    url = "https://fund.eastmoney.com/data/FundDataPortfolio_Interface.aspx"
    params = {
        "dt": "11",
        "pi": "1",
        "pn": "50",
        "mc": "hypzDetail",
        "st": "desc",
        "sc": "reportdate",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    data_json = demjson.decode(data_text[data_text.find("{") : -1])
    total_page = data_json["pages"]
    big_df = pd.DataFrame()
    for page in range(1, int(total_page) + 1):
        params.update({"pi": page})
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = demjson.decode(data_text[data_text.find("{") : -1])
        temp_df = pd.DataFrame(data_json["data"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = big_df["index"] + 1
    big_df.columns = [
        "序号",
        "截止日期",
        "基金家数",
        "机构持有比列",
        "个人持有比列",
        "内部持有比列",
        "总份额",
    ]
    big_df["截止日期"] = pd.to_datetime(big_df["截止日期"], errors="coerce").dt.date
    big_df["基金家数"] = pd.to_numeric(big_df["基金家数"], errors="coerce")
    big_df["机构持有比列"] = pd.to_numeric(big_df["机构持有比列"], errors="coerce")
    big_df["个人持有比列"] = pd.to_numeric(big_df["个人持有比列"], errors="coerce")
    big_df["内部持有比列"] = pd.to_numeric(big_df["内部持有比列"], errors="coerce")
    big_df["总份额"] = pd.to_numeric(
        big_df["总份额"].str.replace(",", ""), errors="coerce"
    )
    return big_df


if __name__ == "__main__":
    fund_scale_change_em_df = fund_scale_change_em()
    print(fund_scale_change_em_df)

    fund_hold_structure_em_df = fund_hold_structure_em()
    print(fund_hold_structure_em_df)
