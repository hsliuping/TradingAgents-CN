# -*- coding:utf-8 -*-
"""
    证券系统元方法，如获取交易日等
"""
import time
import zlib
import baostock.data.resultset as rs
import baostock.common.contants as cons
import baostock.util.stringutil as strUtil
import baostock.common.context as conx
import baostock.util.socketutil as sock
import baostock.data.messageheader as msgheader


def query_trade_dates(start_date=None, end_date=None):
    """查询出给定范围的交易日信息

    @param start_date: 起始日期，默认2015-01-01
    @param end_date: 终止日期，默认当前日期
    @return: calendar_date 日期；is_trading_day，是否交易日，0:非交易日;1:交易日
    """
    data = rs.ResultData()

    if start_date is None or start_date == "":
        start_date = cons.DEFAULT_START_DATE
    if end_date is None or end_date == "":
        end_date = time.strftime("%Y-%m-%d", time.localtime())

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "%s,%s,%s,%s,%s,%s" % (
        "query_trade_dates", user_id, "1",
        cons.BAOSTOCK_PER_PAGE_COUNT, start_date, end_date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYTRADEDATES_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYTRADEDATES_REQUEST
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
        data.start_date = body_arr[7]
        data.end_date = body_arr[8]
        data.setFields(body_arr[9])

    return data


def query_all_stock(day=None):
    """查询给定日期的所有证券信息，

    @param day: 默认当前日期
    """
    data = rs.ResultData()

    if day is None or day == "":
        day = time.strftime("%Y-%m-%d", time.localtime())

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "%s,%s,%s,%s,%s" % (
        "query_all_stock", user_id, "1",
        cons.BAOSTOCK_PER_PAGE_COUNT, day)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYALLSTOCK_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYALLSTOCK_REQUEST
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
        data.day = body_arr[7]
        data.setFields(body_arr[8])

    return data


def query_stock_basic(code="", code_name=""):
    """A股证券基本资料
    @param code: 证券代码，可为空
    @param code_name: 证券名称，可为空，支持模糊查询
    """
    data = rs.ResultData()

    if code is None or code == "":
        code = ""
    if code != "" and code is not None:
        if len(code) != cons.STOCK_CODE_LENGTH:
            print("股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。")
            data.error_msg = "股票代码应为" + str(cons.STOCK_CODE_LENGTH) + "位，请检查。格式示例：sh.600000。"
            data.error_code = cons.BSERR_PARAM_ERR
            return data
        code = code.lower()
        if (code.endswith("sh") or code.endswith("sz")):
            code = code[7:9].lower() + "." + code[0:6]

    if code_name is None or code_name == "":
        code_name = ""

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_stock_basic," + str(user_id) + ",1," + \
        str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
        "," + str(code) + "," + str(code_name)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYSTOCKBASIC_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYSTOCKBASIC_REQUEST
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
        data.code_name = body_arr[8]
        data.setFields(body_arr[9])

    return data
