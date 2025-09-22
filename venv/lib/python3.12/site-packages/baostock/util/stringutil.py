# -*- coding:utf-8 -*-
"""
字符串方法
@author: baostock.com
@group : baostock.com
@contact: baostock@163.com
"""
import datetime
import baostock.common.contants as cons


def add_zero_for_string(content, length, direction):
    """在str的左或右添加0
    :param str:待修改的字符串
    :param length:总共的长度
    :param direction:方向，True左，False右
    :return:
    """
    content = str(content)
    str_len = len(content)
    if str_len < length:
        while str_len < length:
            if direction:
                content = "0" + content
            else:
                content = content + "0"

            str_len = len(content)
    return content


def is_valid_date(str):
    """判断是否是一个有效的日期字符串
    :param str:
    :return: 符合格式返回True,
    """
    try:
        datetime.datetime.strptime(str, "%Y-%m-%d")
        return True
    except Exception:
        return False


def is_valid_year_date(str):
    """判断是否是一个有效的年日期字符串：yyyy
    :param str:
    :return: 符合格式返回True,
    """
    try:
        datetime.datetime.strptime(str, "%Y")
        return True
    except Exception:
        return False


def is_valid_year_month_date(str):
    """判断是否是一个有效的年月日期字符串：yyyy-mm
    :param str:
    :return: 符合格式返回True,
    """
    try:
        datetime.datetime.strptime(str, "%Y-%m")
        return True
    except Exception:
        return False


def organize_msg_body(str):
    """根据传入的信息，组织消息头，并返回"""
    str_arr = str.split(",")
    msg_body = ""  # 返回的消息头
    for item in str_arr:
        msg_body = msg_body + item.strip() + cons.MESSAGE_SPLIT
    return msg_body[0:len(msg_body) - 1]


def organize_realtime_msg_body(str):
    """根据传入的信息，组织消息头，并返回"""
    str_arr = str.split(cons.MESSAGE_SPLIT)
    msg_body = ""  # 返回的消息头
    for item in str_arr:
        msg_body = msg_body + item.strip() + cons.MESSAGE_SPLIT
    return msg_body[0:len(msg_body) - 1]
