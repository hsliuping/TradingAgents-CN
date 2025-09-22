#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/7/6 18:00
Desc: openctp 期货交易费用参照表
http://openctp.cn/fees.html
"""

from datetime import datetime
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup


def futures_fees_info() -> pd.DataFrame:
    """
    openctp 期货交易费用参照表
    http://openctp.cn/fees.html
    :return: 期货交易费用参照表
    :rtype: pandas.DataFrame
    """
    url = "http://openctp.cn/fees.html"
    r = requests.get(url)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, features="lxml")
    datetime_str = soup.find("p").string.strip("Generated at ").strip(".")
    datetime_raw = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
    temp_df = pd.read_html(StringIO(r.text))[0]
    temp_df["更新时间"] = datetime_raw.strftime("%Y-%m-%d %H:%M:%S")
    return temp_df


if __name__ == "__main__":
    futures_fees_info_df = futures_fees_info()
    print(futures_fees_info_df)
