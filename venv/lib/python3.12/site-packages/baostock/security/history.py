# -*- coding:utf-8 -*-
"""
获取历史行情
@author: baostock.com
@group : baostock.com
@contact: baostock@163.com
"""
import datetime
import time
import zlib

import baostock.common.contants as cons
import baostock.common.context as conx
import baostock.data.messageheader as msgheader
import baostock.data.resultset as rs
import baostock.util.socketutil as sock
import baostock.util.stringutil as strUtil


def query_history_k_data_plus(code, fields, start_date=None, end_date=None,
                              frequency='d', adjustflag='3'):
    """获取历史K线plus"""
    return __query_history_k_data_plus_page(1, cons.BAOSTOCK_PER_PAGE_COUNT, code, fields, start_date,
                                            end_date, frequency, adjustflag)


def __query_history_k_data_plus_page(cur_page_num, per_page_count, code, fields,
                                     start_date, end_date, frequency, adjustflag):
    """获取历史K线，私有方法"""
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
    if fields is None or fields == "":
        data.error_msg = "指示简称不能为空，请检查。"
        data.error_code = cons.BSERR_PARAM_ERR
        print("指示简称不能为空，请检查。")
        return data

    if start_date is None or start_date == "":
        start_date = cons.DEFAULT_START_DATE
    if end_date is None or end_date == "":
        end_date = time.strftime("%Y-%m-%d", time.localtime())

    if start_date != "" and end_date != "":
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

    if frequency is None or frequency == "":
        print("数据类型（frequency）不可为空，请检查。")
        data.error_msg = "数据类型（frequency）不可为空，请检查"
        data.error_code = cons.BSERR_PARAM_ERR
        return data
    if adjustflag is None or adjustflag == "":
        print("复权类型（adjustflag）不可为空，请检查。")
        data.error_msg = "复权类型（adjustflag）不可为空，请检查。"
        data.error_code = cons.BSERR_PARAM_ERR
        return data

    user_id = ""
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    msg_body = "query_history_k_data_plus" + cons.MESSAGE_SPLIT + user_id + cons.MESSAGE_SPLIT \
               + str(cur_page_num) + cons.MESSAGE_SPLIT + str(per_page_count) + cons.MESSAGE_SPLIT + code \
               + cons.MESSAGE_SPLIT + fields + cons.MESSAGE_SPLIT + start_date \
               + cons.MESSAGE_SPLIT + end_date + cons.MESSAGE_SPLIT + frequency \
               + cons.MESSAGE_SPLIT + adjustflag

    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_GETKDATAPLUS_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_GETKDATAPLUS_REQUEST
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

    # data.version = header_arr[0]
    # data.msg_type = header_arr[1]
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
        data.setFields(body_arr[8])
        data.start_date = body_arr[9]
        data.end_date = body_arr[10]
        data.frequency = body_arr[11]
        data.adjustflag = body_arr[12]

    return data
