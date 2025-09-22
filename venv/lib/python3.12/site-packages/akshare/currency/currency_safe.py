# -*- coding:utf-8 -*-
# !/usr/bin/env python
"""
Date: 2024/4/29 17:00
Desc: 人民币汇率中间价
https://www.safe.gov.cn/safe/rmbhlzjj/index.html
"""

import re
from datetime import datetime
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup


def currency_boc_safe() -> pd.DataFrame:
    """
    人民币汇率中间价
    https://www.safe.gov.cn/safe/rmbhlzjj/index.html
    :return: 人民币汇率中间价
    :rtype: pandas.DataFrame
    """
    url = "https://www.safe.gov.cn/safe/2020/1218/17833.html"
    r = requests.get(url)
    r.encoding = "utf8"
    soup = BeautifulSoup(r.text, features="lxml")
    content = soup.find(name="a", string=re.compile("人民币汇率"))["href"]
    url = f"https://www.safe.gov.cn{content}"
    temp_df = pd.read_excel(url)
    temp_df.sort_values(by=["日期"], inplace=True)
    temp_df.reset_index(inplace=True, drop=True)
    start_date = (
        (pd.Timestamp(temp_df["日期"].tolist()[-1]) + pd.Timedelta(days=1))
        .isoformat()
        .split("T")[0]
    )
    end_date = datetime.now().isoformat().split("T")[0]
    url = "https://www.safe.gov.cn/AppStructured/hlw/RMBQuery.do"
    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "queryYN": "true",
    }
    r = requests.post(url, data=payload)
    current_temp_df = pd.read_html(StringIO(r.text))[-1]
    current_temp_df.sort_values(by=["日期"], inplace=True)
    current_temp_df.reset_index(inplace=True, drop=True)
    big_df = pd.concat(objs=[temp_df, current_temp_df], ignore_index=True)
    column_name_list = big_df.columns[1:]
    for item in column_name_list:
        big_df[item] = pd.to_numeric(big_df[item], errors="coerce")
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    return big_df


if __name__ == "__main__":
    currency_boc_safe_df = currency_boc_safe()
    print(currency_boc_safe_df)
