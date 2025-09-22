# -*- coding:utf-8 -*-
"""
大类：公司公告，小类：公司业绩报告
@author: baostock.com
@group : baostock.com
@contact: baostock@163.com
@copyright: baostock System & alpha.All Rights Reserved.
"""

import datetime
import time
import zlib

import baostock.data.resultset as rs
import baostock.common.contants as cons
import baostock.util.stringutil as strUtil
import baostock.common.context as conx
import baostock.util.socketutil as sock
import baostock.data.messageheader as msgheader


def query_performance_express_report(code, start_date=None, end_date=None):
    """公司业绩快报。
    @param code: 证券代码，不可为空
    @param start_date: 开始日期，默认2015-01-01；发布日期或更新日期在这个范围内。
    @param end_date: 结束日期，默认系统当前日期；发布日期或更新日期在这个范围内。
    """

    data = rs.ResultData()
    if code is None or code == "":
        print("股票代码不能为空，请检查。")
        data.error_msg = "股票代码不能为空，请检查。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    if len(code) != cons.STOCK_CODE_LENGTH:
        print("股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。")
        data.error_msg = "股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    code = code.lower()
    if (code.endswith("sh") or code.endswith("sz")):
        code = code[7:9].lower() + "." + code[0:6]

    if start_date is None or start_date == "":
        start_date = cons.DEFAULT_START_DATE
    if end_date is None or end_date == "":
        end_date = time.strftime("%Y-%m-%d", time.localtime())

    if start_date != "" and start_date is not None and end_date != "" and end_date is not None:
        if strUtil.is_valid_date(start_date) and strUtil.is_valid_date(end_date):
            start_date_time = datetime.datetime.strptime(
                start_date, '%Y-%m-%d')
            end_date_time = datetime.datetime.strptime(end_date, '%Y-%m-%d')
            if end_date_time < start_date_time:
                print("起始日期大于终止日期，请修改。")
                data.error_code = cons.BSERR_START_BIGTHAN_END
                data.error_msg = "起始日期大于终止日期，请修改。"
                return data
        else:
            print("日期格式不正确，请修改。")
            return

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "%s,%s,%s,%s,%s,%s,%s" % (
        "query_performance_express_report", user_id, "1",
        cons.BAOSTOCK_PER_PAGE_COUNT, code, start_date, end_date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYPERFORMANCEEXPRESSREPORT_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYPERFORMANCEEXPRESSREPORT_REQUEST
    data.msg_body = msg_body

    head_body = msg_header + msg_body
    crc32str = zlib.crc32(bytes(head_body, encoding='utf-8'))
    receive_data = sock.send_msg(head_body + cons.MESSAGE_SPLIT + str(crc32str))

    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"
        return data

    msg_header = receive_data[0:cons.MESSAGE_HEADER_LENGTH]
    msg_body = receive_data[cons.MESSAGE_HEADER_LENGTH:-1]
    header_arr = msg_header.split(cons.MESSAGE_SPLIT)
    body_arr = msg_body.split(cons.MESSAGE_SPLIT)
    data.msg_body_length = header_arr[2]
    data.error_code = body_arr[0]
    data.error_msg = body_arr[1]

    if cons.BSERR_SUCCESS == data.error_code:
        data.method = body_arr[2]
        data.user_id = body_arr[3]
        data.cur_page_num = body_arr[4]
        data.per_page_count = body_arr[5]
        data.setData(body_arr[6])
        data.code = body_arr[7]
        data.start_date = body_arr[8]
        data.end_date = body_arr[9]
        data.setFields(body_arr[10])

    return data


def query_forecast_report(code, start_date=None, end_date=None):
    """公司业绩预告，
    @param code: 证券代码，不可为空
    @param start_date: 开始日期，默认2015-01-01；发布日期或统计日期在这个范围内。
    @param end_date: 结束日期，默认系统当前日期；发布日期或统计日期在这个范围内。
    """
    data = rs.ResultData()
    if code is None or code == "":
        print("股票代码不能为空，请检查。")
        data.error_msg = "股票代码不能为空，请检查。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    if len(code) != cons.STOCK_CODE_LENGTH:
        print("股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。")
        data.error_msg = "股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    code = code.lower()
    if (code.endswith("sh") or code.endswith("sz")):
        code = code[7:9].lower() + "." + code[0:6]

    if start_date is None or start_date == "":
        start_date = cons.DEFAULT_START_DATE
    if end_date is None or end_date == "":
        end_date = time.strftime("%Y-%m-%d", time.localtime())

    if start_date != "" and start_date is not None and end_date != "" and end_date is not None:
        if strUtil.is_valid_date(start_date) and strUtil.is_valid_date(end_date):
            start_date_time = datetime.datetime.strptime(
                start_date, '%Y-%m-%d')
            end_date_time = datetime.datetime.strptime(end_date, '%Y-%m-%d')
            if end_date_time < start_date_time:
                print("起始日期大于终止日期，请修改。")
                data.error_code = cons.BSERR_START_BIGTHAN_END
                data.error_msg = "起始日期大于终止日期，请修改。"
                return data
        else:
            print("日期格式不正确，请修改。")
            return

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "%s,%s,%s,%s,%s,%s,%s" % (
        "query_forecast_report", user_id, "1",
        cons.BAOSTOCK_PER_PAGE_COUNT, code, start_date, end_date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYFORECASTREPORT_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYFORECASTREPORT_REQUEST
    data.msg_body = msg_body

    head_body = msg_header + msg_body
    crc32str = zlib.crc32(bytes(head_body, encoding='utf-8'))
    receive_data = sock.send_msg(head_body + cons.MESSAGE_SPLIT + str(crc32str))

    if receive_data is None or receive_data.strip() == "":
        data.error_code = cons.BSERR_RECVSOCK_FAIL
        data.error_msg = "网络接收错误。"
        return data

    msg_header = receive_data[0:cons.MESSAGE_HEADER_LENGTH]
    msg_body = receive_data[cons.MESSAGE_HEADER_LENGTH:-1]
    header_arr = msg_header.split(cons.MESSAGE_SPLIT)
    body_arr = msg_body.split(cons.MESSAGE_SPLIT)
    data.msg_body_length = header_arr[2]
    data.error_code = body_arr[0]
    data.error_msg = body_arr[1]

    if cons.BSERR_SUCCESS == data.error_code:
        data.method = body_arr[2]
        data.user_id = body_arr[3]
        data.cur_page_num = body_arr[4]
        data.per_page_count = body_arr[5]
        data.setData(body_arr[6])
        data.code = body_arr[7]
        data.start_date = body_arr[8]
        data.end_date = body_arr[9]
        data.setFields(body_arr[10])

    return data
