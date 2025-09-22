#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2025/3/22 16:30
Desc: 郑州商品交易所-交易数据-历史行情下载-期权历史行情下载
http://www.czce.com.cn/cn/jysj/lshqxz/H770319index_1.htm
自 20200101 起，成交量、空盘量、成交额、行权量均为单边计算
郑州商品交易所-期权上市时间表
"SR": "20170419"
"CF": "20190410"
"TA": "20191216"
"MA": "20191217"
"RM": "20200116"
"ZC": "20200630"
"OI": "20220826"
"PK": "20220826"
"PX": "20230915"
"SH": "20230915"
"SA": "20231020"
"PF": "20231020"
"SM": "20231020"
"SF": "20231020"
"UR": "20231020"
"AP": "20231020"
"CJ": "20240621"
"FG": "20240621"
"PR": "20241227"
"""

from io import StringIO
import warnings

import pandas as pd
import requests


def option_czce_hist(symbol: str = "SR", year: str = "2021") -> pd.DataFrame:
    """
    郑州商品交易所-交易数据-历史行情下载-期权历史行情下载
    http://www.czce.com.cn/cn/jysj/lshqxz/H770319index_1.htm
    :param symbol: choice of {"白糖": "SR", "棉花": "CF", "PTA": "TA", "甲醇": "MA", "菜籽粕": "RM",
    "动力煤": "ZC", "菜籽油": "OI", "花生": "PK", "对二甲苯": "PX", "烧碱": "SH", "纯碱": "SA", "短纤": "PF",
    "锰硅": "SM", "硅铁": "SF", "尿素": "UR", "苹果": "AP", "红枣": "CJ", "玻璃": "FG", "瓶片": "PR"}
    :type symbol: str
    :param year: 需要获取数据的年份, 注意品种的上市时间
    :type year: str
    :return: 指定年份的日频期权数据
    :rtype: pandas.DataFrame
    """
    symbol_year_dict = {
        "SR": "2017",
        "CF": "2019",
        "TA": "2019",
        "MA": "2019",
        "RM": "2020",
        "ZC": "2020",
        "OI": "2022",
        "PK": "2022",
        "PX": "2023",
        "SH": "2023",
        "SA": "2023",
        "PF": "2023",
        "SM": "2023",
        "SF": "2023",
        "UR": "2023",
        "AP": "2023",
        "CJ": "2024",
        "FG": "2024",
        "PR": "2024",
    }
    if int(symbol_year_dict[symbol]) > int(year):
        warnings.warn(f"{year} year, symbol {symbol} is not on trade")
        return pd.DataFrame()
    url = f"http://www.czce.com.cn/cn/DFSStaticFiles/Option/{year}/OptionDataAllHistory/{symbol}OPTIONS{year}.txt"
    r = requests.get(url)
    option_df = pd.read_table(StringIO(r.text), skiprows=1, sep="|", low_memory=False)
    return option_df


if __name__ == "__main__":
    option_czce_hist_df = option_czce_hist(symbol="RM", year="2025")
    print(option_czce_hist_df)
