#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
token 验证
Created on 2023/12/06
@author: Monday
@group : waditu
@contact:
"""
import datetime


def timestemp_to_time(time_stamp, form_date="%Y-%m-%d %H:%M:%S"):
    time_stamp = int(str(time_stamp)[0:10])
    date_array = datetime.datetime.fromtimestamp(time_stamp)
    other_style_time = date_array.strftime(form_date)
    return str(other_style_time)


def get_current_date(date_format='%Y-%m-%d %H:%M:%S', hours_num=0, minutes_num=0, is_time=False):
    """hours_num -1 #获取前一小时  +1  后一个小时"""
    if hours_num == 0 and minutes_num == 0:
        current_time = datetime.datetime.now().strftime(date_format)
    elif hours_num != 0 and minutes_num == 0:
        current_time = (datetime.datetime.now() + datetime.timedelta(hours=hours_num)).strftime(date_format)
    else:
        current_time = (datetime.datetime.now() + datetime.timedelta(minutes=minutes_num)).strftime(date_format)
    if not is_time:
        return current_time
    else:
        return datetime.datetime.strptime(current_time, date_format)
