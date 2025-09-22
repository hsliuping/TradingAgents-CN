#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/3/25 16:30
Desc: 新浪财经-交易日历
https://finance.sina.com.cn/realstock/company/klc_td_sh.txt
此处可以用来更新 calendar.json 文件，注意末尾没有 "," 号
"""

import datetime

import pandas as pd
import requests
import py_mini_racer

from akshare.stock.cons import hk_js_decode


def tool_trade_date_hist_sina() -> pd.DataFrame:
    """
    新浪财经-交易日历-历史数据
    https://finance.sina.com.cn/realstock/company/klc_td_sh.txt
    :return: 交易日历
    :rtype: pandas.DataFrame
    """
    url = "https://finance.sina.com.cn/realstock/company/klc_td_sh.txt"
    r = requests.get(url)
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(hk_js_decode)
    dict_list = js_code.call("d", r.text.split("=")[1].split(";")[0].replace('"', ""))
    temp_df = pd.DataFrame(dict_list)
    temp_df.columns = ["trade_date"]
    temp_df["trade_date"] = pd.to_datetime(temp_df["trade_date"]).dt.date
    temp_list = temp_df["trade_date"].to_list()
    # 该日期是交易日，但是在新浪返回的交易日历缺失该日期，这里补充上
    temp_list.append(datetime.date(year=1992, month=5, day=4))
    temp_list.sort()
    temp_df = pd.DataFrame(temp_list, columns=["trade_date"])
    return temp_df


if __name__ == "__main__":
    tool_trade_date_hist_df = tool_trade_date_hist_sina()
    print(tool_trade_date_hist_df)
