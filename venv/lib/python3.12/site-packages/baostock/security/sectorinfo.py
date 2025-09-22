# -*- coding:utf-8 -*-
"""
获行业分类
@author: baostock.com
@group : baostock.com
@contact: baostock@163.com
"""

import zlib
import baostock.data.resultset as rs
import baostock.common.contants as cons
import baostock.util.stringutil as strUtil
import baostock.common.context as conx
import baostock.util.socketutil as sock
import baostock.data.messageheader as msgheader


def query_stock_industry(code="", date=""):
    """获取行业分类
    @param code：股票代码，默认为空。
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
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

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx,"user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_stock_industry," + str(user_id) + ",1," + \
        str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
        "," + str(code) + "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYSTOCKINDUSTRY_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYSTOCKINDUSTRY_REQUEST
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
        data.date = body_arr[8]
        data.setFields(body_arr[9])

    return data


def query_hs300_stocks(date=""):
    """获取沪深300成分股
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
    """
    data = rs.ResultData()

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx, "user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_hs300_stocks," + str(user_id) + ",1," + \
            str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
            "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYHS300STOCKS_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYHS300STOCKS_REQUEST
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
        data.date = body_arr[7]
        data.setFields(body_arr[8])

    return data


def query_sz50_stocks(date=""):
    """获取上证50成分股
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
    """
    data = rs.ResultData()

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data    
    user_id = getattr(conx, "user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_sz50_stocks," + str(user_id) + ",1," + \
            str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
            "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYSZ50STOCKS_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYSZ50STOCKS_REQUEST
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
        data.date = body_arr[7]
        data.setFields(body_arr[8])

    return data


def query_zz500_stocks(date=""):
    """获取中证500成分股
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
    """
    data = rs.ResultData()

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx, "user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_zz500_stocks," + str(user_id) + ",1," + \
            str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
            "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYZZ500STOCKS_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYZZ500STOCKS_REQUEST
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
        data.date = body_arr[7]
        data.setFields(body_arr[8])

    return data

def query_terminated_stocks(date=""):
    """获取终止上市股票列表
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
    """
    data = rs.ResultData()

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx, "user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_terminated_stocks," + str(user_id) + ",1," + \
            str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
            "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYTERMINATEDSTOCKS_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYTERMINATEDSTOCKS_REQUEST
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
        data.date = body_arr[7]
        data.setFields(body_arr[8])

    return data

def query_suspended_stocks(date=""):
    """获取暂停上市股票列表
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
    """
    data = rs.ResultData()

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx, "user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_suspended_stocks," + str(user_id) + ",1," + \
            str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
            "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYSUSPENDEDSTOCKS_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYSUSPENDEDSTOCKS_REQUEST
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
        data.date = body_arr[7]
        data.setFields(body_arr[8])

    return data

def query_st_stocks(date=""):
    """获取ST股票列表
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
    """
    data = rs.ResultData()

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx, "user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_st_stocks," + str(user_id) + ",1," + \
            str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
            "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYSTSTOCKS_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYSTSTOCKS_REQUEST
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
        data.date = body_arr[7]
        data.setFields(body_arr[8])

    return data

def query_starst_stocks(date=""):
    """获取*ST股票列表
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
    """
    data = rs.ResultData()

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx, "user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_starst_stocks," + str(user_id) + ",1," + \
            str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
            "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYSTARSTSTOCKS_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYSTARSTSTOCKS_REQUEST
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
        data.date = body_arr[7]
        data.setFields(body_arr[8])

    return data


def query_stock_concept(code="", date=""):
    """获取概念分类
    @param code：股票代码，默认为空。
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
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

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx,"user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_stock_concept," + str(user_id) + ",1," + \
        str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
        "," + str(code) + "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYSTOCKCONCEPT_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYSTOCKCONCEPT_REQUEST
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
        data.date = body_arr[8]
        data.setFields(body_arr[9])

    return data

def query_stock_area(code="", date=""):
    """获取地域分类
    @param code：股票代码，默认为空。
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
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

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx,"user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_stock_area," + str(user_id) + ",1," + \
        str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
        "," + str(code) + "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYSTOCKAREA_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYSTOCKAREA_REQUEST
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
        data.date = body_arr[8]
        data.setFields(body_arr[9])

    return data


def query_ame_stocks(date=""):
    """获取中小板分类
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
    """
    data = rs.ResultData()

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx, "user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_ame_stocks," + str(user_id) + ",1," + \
            str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
            "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYAMESTOCK_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYAMESTOCK_REQUEST
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
        data.date = body_arr[7]
        data.setFields(body_arr[8])

    return data

def query_gem_stocks(date=""):
    """获取创业板分类
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
    """
    data = rs.ResultData()

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx, "user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_gem_stocks," + str(user_id) + ",1," + \
            str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
            "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYGEMSTOCK_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYGEMSTOCK_REQUEST
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
        data.date = body_arr[7]
        data.setFields(body_arr[8])

    return data

def query_shhk_stocks(date=""):
    """获取沪港通股票
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
    """
    data = rs.ResultData()

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
        
    user_id = getattr(conx, "user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_shhk_stocks," + str(user_id) + ",1," + \
            str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
            "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYSHHKSTOCK_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYSHHKSTOCK_REQUEST
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
        data.date = body_arr[7]
        data.setFields(body_arr[8])

    return data

def query_szhk_stocks(date=""):
    """获取深港通股票
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
    """
    data = rs.ResultData()

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx, "user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_szhk_stocks," + str(user_id) + ",1," + \
            str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
            "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYSZHKSTOCK_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYSZHKSTOCK_REQUEST
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
        data.date = body_arr[7]
        data.setFields(body_arr[8])

    return data

def query_stocks_in_risk(date=""):
    """获取风险警示板分类
    @param date：查询日期，默认为空。不为空时，格式 XXXX-XX-XX。
    """
    data = rs.ResultData()

    if date is None or date == "":
        date = ""
    else:
        if strUtil.is_valid_date(date):
            pass
        else:
            print("日期格式不正确，请修改。")
            data.error_code = cons.BSERR_DATE_ERR
            data.error_msg = "日期格式不正确，请修改。"
            return data
    user_id = getattr(conx, "user_id")
    try:
        user_id = getattr(conx, "user_id")
    except Exception:
        print("you don't login.")
        data.error_code = cons.BSERR_NO_LOGIN
        data.error_msg = "you don't login."
        return data

    param = "query_stocks_in_risk," + str(user_id) + ",1," + \
            str(cons.BAOSTOCK_PER_PAGE_COUNT) + \
            "," + str(date)

    msg_body = strUtil.organize_msg_body(param)
    msg_header = msgheader.to_message_header(
        cons.MESSAGE_TYPE_QUERYSTOCKINRISK_REQUEST, len(msg_body))

    data.msg_type = cons.MESSAGE_TYPE_QUERYSTOCKINRISK_REQUEST
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
        data.date = body_arr[7]
        data.setFields(body_arr[8])

    return data
