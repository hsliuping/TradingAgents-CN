# coding:utf-8
from .trade_date import trade_date_sse

import datetime


def get_real_trade_date(date, towards):
    """
    获取真实的交易日期,其中,第三个参数towards是表示向前/向后推
    towards=1 日期向后迭代
    towards=-1 日期向前迭代
    @yutiansut
    """
    if towards == 1:
        while date not in trade_date_sse:
            date = str(datetime.datetime.strptime(
                date, '%Y-%m-%d') + datetime.timedelta(days=1))[0:10]
        else:
            return date
    elif towards == -1:
        while date not in trade_date_sse:
            date = str(datetime.datetime.strptime(
                date, '%Y-%m-%d') - datetime.timedelta(days=1))[0:10]
        else:
            return date
