#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2019/9/30 13:58
Desc: 期权配置文件
"""

import datetime
import json
import os
import re

# 中国金融期货交易所

CFFEX_OPTION_URL_300 = "http://www.cffex.com.cn/quote_IO.txt"

# 深圳证券交易所

SZ_OPTION_URL_300 = "http://www.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID=ysplbrb&TABKEY=tab1&random=0.10432465776720479"

# 上海证券交易所

SH_OPTION_URL_50 = "http://yunhq.sse.com.cn:32041/v1/sh1/list/self/510050"
SH_OPTION_URL_KING_50 = "http://yunhq.sse.com.cn:32041/v1/sho/list/tstyle/510050_{}"

SH_OPTION_URL_300 = "http://yunhq.sse.com.cn:32041/v1/sh1/list/self/510300"
SH_OPTION_URL_KING_300 = "http://yunhq.sse.com.cn:32041/v1/sho/list/tstyle/510300_{}"

SH_OPTION_URL_500 = "http://yunhq.sse.com.cn:32041/v1/sh1/list/self/510500"
SH_OPTION_URL_KING_500 = "http://yunhq.sse.com.cn:32041/v1/sho/list/tstyle/510500_{}"

SH_OPTION_URL_KC_50 = "http://yunhq.sse.com.cn:32041/v1/sh1/list/self/588000"
SH_OPTION_URL_KC_KING_50 = "http://yunhq.sse.com.cn:32041/v1/sho/list/tstyle/588000_{}"

SH_OPTION_URL_KC_50_YFD = "http://yunhq.sse.com.cn:32041/v1/sh1/list/self/588080"
SH_OPTION_URL_KING_50_YFD = "http://yunhq.sse.com.cn:32041/v1/sho/list/tstyle/588080_{}"

SH_OPTION_PAYLOAD = {
    "select": "select: code,name,last,change,chg_rate,amp_rate,volume,amount,prev_close"
}

SH_OPTION_PAYLOAD_OTHER = {"select": "contractid,last,chg_rate,presetpx,exepx"}


# 大连商品交易所
DCE_OPTION_URL = "http://www.dce.com.cn/publicweb/quotesdata/dayQuotesCh.html"
DCE_DAILY_OPTION_URL = (
    "http://www.dce.com.cn/publicweb/quotesdata/exportDayQuotesChData.html"
)

# 上海期货交易所
SHFE_OPTION_URL = "https://tsite.shfe.com.cn/data/dailydata/option/kx/kx{}.dat"

# 郑州商品交易所
CZCE_DAILY_OPTION_URL_3 = (
    "http://www.czce.com.cn/cn/DFSStaticFiles/Option/{}/{}/OptionDataDaily.txt"
)

# PAYLOAD
SHFE_HEADERS = {"User-Agent": "Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)"}

DATE_PATTERN = re.compile(r"^([0-9]{4})[-/]?([0-9]{2})[-/]?([0-9]{2})")


def convert_date(date):
    """
    transform a date string to datetime.date object
    :param date, string, e.g. 2016-01-01, 20160101 or 2016/01/01
    :return: object of datetime.date(such as 2016-01-01) or None
    """
    if isinstance(date, datetime.date):
        return date
    elif isinstance(date, str):
        match = DATE_PATTERN.match(date)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                return datetime.date(
                    year=int(groups[0]), month=int(groups[1]), day=int(groups[2])
                )
    return None


def get_json_path(name, module_file):
    """
    获取 JSON 配置文件的路径(从模块所在目录查找)
    :param name: 文件名
    :param module_file: filename
    :return: str json_file_path
    """
    module_folder = os.path.abspath(os.path.dirname(os.path.dirname(module_file)))
    module_json_path = os.path.join(module_folder, "file_fold", name)
    return module_json_path


def get_calendar():
    """
    获取交易日历至 2019 年结束, 这里的交易日历需要按年更新
    :return: json
    """
    setting_file_name = "calendar.json"
    setting_file_path = get_json_path(setting_file_name, __file__)
    return json.load(open(setting_file_path, "r"))


def last_trading_day(day):
    """
    获取前一个交易日
    :param day: "%Y%m%d" or  datetime.date()
    :return last_day: "%Y%m%d" or  datetime.date()
    """
    calendar = get_calendar()

    if isinstance(day, str):
        if day not in calendar:
            print("Today is not trading day：" + day)
            return False
        pos = calendar.index(day)
        last_day = calendar[pos - 1]
        return last_day

    elif isinstance(day, datetime.date):
        d_str = day.strftime("%Y%m%d")
        if d_str not in calendar:
            print("Today is not working day：" + d_str)
            return False
        pos = calendar.index(d_str)
        last_day = calendar[pos - 1]
        last_day = datetime.datetime.strptime(last_day, "%Y%m%d").date()
        return last_day


def get_latest_data_date(day):
    """
    获取最新的有数据的交易日
    :param day: datetime.datetime
    :return string YYYYMMDD
    """
    calendar = get_calendar()
    if day.strftime("%Y%m%d") in calendar:
        if day.time() > datetime.time(17, 0, 0):
            return day.strftime("%Y%m%d")
        else:
            return last_trading_day(day.strftime("%Y%m%d"))
    else:
        while day.strftime("%Y%m%d") not in calendar:
            day = day - datetime.timedelta(days=1)
        return day.strftime("%Y%m%d")


if __name__ == "__main__":
    d = datetime.datetime(2018, 10, 5, 17, 1, 0)
    print(get_latest_data_date(d))
