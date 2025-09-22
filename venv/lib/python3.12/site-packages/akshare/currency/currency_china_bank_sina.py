#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2023/11/10 15:20
Desc: 新浪财经-中行人民币牌价历史数据查询
https://biz.finance.sina.com.cn/forex/forex.php?startdate=2012-01-01&enddate=2021-06-14&money_code=EUR&type=0
"""

from functools import lru_cache
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


@lru_cache()
def _currency_boc_sina_map(
    start_date: str = "20210614", end_date: str = "20230810"
) -> dict:
    """
    外汇 symbol 和代码映射
    https://biz.finance.sina.com.cn/forex/forex.php?startdate=2012-01-01&enddate=2021-06-14&money_code=EUR&type=0
    :param start_date: 开始交易日
    :type start_date: str
    :param end_date: 结束交易日
    :type end_date: str
    :return: 外汇 symbol 和代码映射
    :rtype: dict
    """
    url = "http://biz.finance.sina.com.cn/forex/forex.php"
    params = {
        "startdate": "-".join([start_date[:4], start_date[4:6], start_date[6:]]),
        "enddate": "-".join([end_date[:4], end_date[4:6], end_date[6:]]),
        "money_code": "EUR",
        "type": "0",
    }
    r = requests.get(url, params=params)
    r.encoding = "gbk"
    soup = BeautifulSoup(r.text, "lxml")
    data_dict = dict(
        zip(
            [
                item.text
                for item in soup.find(attrs={"id": "money_code"}).find_all("option")
            ],
            [
                item["value"]
                for item in soup.find(attrs={"id": "money_code"}).find_all("option")
            ],
        )
    )
    return data_dict


def currency_boc_sina(
    symbol: str = "美元", start_date: str = "20230304", end_date: str = "20231110"
) -> pd.DataFrame:
    """
    新浪财经-中行人民币牌价历史数据查询
    https://biz.finance.sina.com.cn/forex/forex.php?startdate=2012-01-01&enddate=2021-06-14&money_code=EUR&type=0
    :param symbol: choice of {'美元', '英镑', '欧元', '澳门元', '泰国铢', '菲律宾比索', '港币', '瑞士法郎', '新加坡元', '瑞典克朗', '丹麦克朗', '挪威克朗', '日元', '加拿大元', '澳大利亚元', '新西兰元', '韩国元'}
    :type symbol: str
    :param start_date: 开始交易日
    :type start_date: str
    :param end_date: 结束交易日
    :type end_date: str
    :return: 中行人民币牌价历史数据查询
    :rtype: pandas.DataFrame
    """
    data_dict = _currency_boc_sina_map(start_date=start_date, end_date=end_date)
    url = "http://biz.finance.sina.com.cn/forex/forex.php"
    params = {
        "money_code": data_dict[symbol],
        "type": "0",
        "startdate": "-".join([start_date[:4], start_date[4:6], start_date[6:]]),
        "enddate": "-".join([end_date[:4], end_date[4:6], end_date[6:]]),
        "page": "1",
        "call_type": "ajax",
    }
    r = requests.get(url, params=params)
    soup = BeautifulSoup(r.text, "lxml")
    soup.find(attrs={"id": "money_code"})
    page_element_list = soup.find_all("a", attrs={"class": "page"})
    page_num = int(page_element_list[-2].text) if len(page_element_list) != 0 else 1
    big_df = pd.DataFrame()
    for page in tqdm(range(1, page_num + 1), leave=False):
        params.update({"page": page})
        r = requests.get(url, params=params)
        temp_df = pd.read_html(StringIO(r.text), header=0)[0]
        big_df = pd.concat([big_df, temp_df], ignore_index=True)
    big_df.columns = [
        "日期",
        "中行汇买价",
        "中行钞买价",
        "中行钞卖价/汇卖价",
        "央行中间价",
    ]
    big_df["日期"] = pd.to_datetime(big_df["日期"], errors="coerce").dt.date
    big_df["中行汇买价"] = pd.to_numeric(big_df["中行汇买价"], errors="coerce")
    big_df["中行钞买价"] = pd.to_numeric(big_df["中行钞买价"], errors="coerce")
    big_df["中行钞卖价/汇卖价"] = pd.to_numeric(
        big_df["中行钞卖价/汇卖价"], errors="coerce"
    )
    big_df["央行中间价"] = pd.to_numeric(big_df["央行中间价"], errors="coerce")
    big_df.sort_values(by=["日期"], inplace=True, ignore_index=True)
    return big_df


if __name__ == "__main__":
    currency_boc_sina_df = currency_boc_sina(
        symbol="美元", start_date="20230304", end_date="20231110"
    )
    print(currency_boc_sina_df)
